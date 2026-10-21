"""Armazenamento do indice: SQLite (metadados) + arquivos binarios.

Arquivos em <indice>/:
  meta.json     dimensao, numero de trechos, tamanhos
  vectors.f32   matriz N x D float32 contigua (sem cabecalho)
  texts.bin     textos dos trechos concatenados (UTF-8)
  offsets.i64   N+1 deslocamentos int64 dos trechos em texts.bin
  chunks.db     SQLite: tabelas docs e chunks

VectorStore carrega os binarios de dois jeitos:
  modo="read": open() + read() do arquivo inteiro para memoria anonima do processo
  modo="mmap": mmap() do arquivo; paginas entram sob demanda (faltas de pagina)
"""
import json
import mmap
import os
import sqlite3
import threading
import time

import numpy as np


class IndiceIndisponivel(Exception):
    pass


def caminhos(indice):
    return {k: os.path.join(indice, v) for k, v in {
        "meta": "meta.json", "vetores": "vectors.f32", "textos": "texts.bin",
        "offsets": "offsets.i64", "db": "chunks.db"}.items()}


def validar_indice(indice):
    p = caminhos(indice)
    for k in ("meta", "vetores", "textos", "offsets", "db"):
        if not os.path.exists(p[k]):
            raise IndiceIndisponivel(f"arquivo do indice ausente: {p[k]}")
    with open(p["meta"]) as f:
        meta = json.load(f)
    esperado = meta["n_trechos"] * meta["dim"] * 4
    real = os.path.getsize(p["vetores"])
    if real != esperado:
        raise IndiceIndisponivel(
            f"vectors.f32 inconsistente: {real} bytes, esperado {esperado} (arquivo truncado?)")
    return meta


class VectorStore:
    def __init__(self, indice, modo="mmap"):
        self.indice = indice
        self.modo = modo
        self.meta = validar_indice(indice)
        self.p = caminhos(indice)
        self.n = self.meta["n_trechos"]
        self.dim = self.meta["dim"]
        self._mm = []
        self._local = threading.local()
        t0 = time.perf_counter()
        self.vetores = self._carregar(self.p["vetores"], np.float32).reshape(self.n, self.dim)
        self.textos = self._carregar_bytes(self.p["textos"])
        self.offsets = self._carregar(self.p["offsets"], np.int64)
        self.t_carga = time.perf_counter() - t0

    def _carregar_bytes(self, path):
        with open(path, "rb") as f:
            if self.modo == "read":
                return f.read()
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            self._mm.append(mm)
            return mm

    def _carregar(self, path, dtype):
        return np.frombuffer(self._carregar_bytes(path), dtype=dtype)

    def buscar(self, qvec, k):
        k = max(1, min(k, self.n))
        scores = self.vetores @ qvec  # percorre a matriz inteira (varredura)
        if k < self.n:
            idx = np.argpartition(-scores, k - 1)[:k]
        else:
            idx = np.arange(self.n)
        idx = idx[np.argsort(-scores[idx])]
        return idx, scores[idx]

    def texto(self, i):
        a = int(self.offsets[i])
        b = int(self.offsets[i + 1])
        return bytes(self.textos[a:b]).decode("utf-8", errors="replace")

    def _conexao(self):
        c = getattr(self._local, "con", None)
        if c is None:
            # uma conexao por thread: objetos sqlite3 nao devem ser compartilhados
            c = sqlite3.connect(f"file:{self.p['db']}?mode=ro", uri=True)
            self._local.con = c
        return c

    def metadados(self, ids):
        con = self._conexao()
        q = ",".join("?" * len(ids))
        cur = con.execute(f"SELECT c.id, d.titulo, d.topico FROM chunks c JOIN docs d "
                          f"ON d.id = c.doc_id WHERE c.id IN ({q})", [int(i) for i in ids])
        return {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    def fechar(self):
        self.vetores = self.offsets = None
        self.textos = None
        for mm in self._mm:
            try:
                mm.close()
            except BufferError:
                pass
