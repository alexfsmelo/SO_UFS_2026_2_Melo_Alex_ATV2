"""Ingestao: le documentos, fragmenta, gera embeddings em lotes e grava o indice."""
import glob
import json
import os
import sqlite3
import time

import numpy as np

from . import metrics
from .embed import HashEmbedder
from .store import caminhos


def fragmentar(texto, tamanho=400, sobreposicao=50):
    """Fragmenta por caracteres respeitando limites de palavra."""
    trechos = []
    i = 0
    n = len(texto)
    while i < n:
        fim = min(n, i + tamanho)
        if fim < n:
            esp = texto.rfind(" ", i + tamanho // 2, fim)
            if esp > 0:
                fim = esp
        trecho = texto[i:fim].strip()
        if trecho:
            trechos.append(trecho)
        if fim >= n:
            break
        i = max(fim - sobreposicao, i + 1)
    return trechos


def ingerir(corpus, indice, dim=256, tamanho=400, sobreposicao=50, lote=4096,
            logger=None, arquivos_extras=()):
    """corpus: pasta com docs/*.txt. arquivos_extras: caminhos adicionais
    (usado para injetar arquivos ausentes no experimento de falha C6)."""
    os.makedirs(indice, exist_ok=True)
    p = caminhos(indice)
    for k in ("vetores", "textos", "offsets", "db"):
        if os.path.exists(p[k]):
            os.remove(p[k])
    arquivos = sorted(glob.glob(os.path.join(corpus, "docs", "*.txt"))) + list(arquivos_extras)
    emb = HashEmbedder(dim)
    con = sqlite3.connect(p["db"])
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE docs (id INTEGER PRIMARY KEY, caminho TEXT, titulo TEXT, "
                "topico TEXT, bytes INTEGER)")
    con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, doc_id INTEGER, ordem INTEGER, "
                "inicio INTEGER, tamanho INTEGER)")
    io0, ru0 = metrics.proc_io(), metrics.rusage()
    t0 = time.perf_counter()
    t_leitura = t_emb = t_escrita = 0.0
    fv = open(p["vetores"], "wb")
    ft = open(p["textos"], "wb")
    offsets = [0]
    pendentes = []  # (texto, doc_id, ordem)
    n_trechos = 0
    falhas = 0
    bytes_corpus = 0
    pico_rss = 0.0

    def descarregar():
        nonlocal n_trechos, t_emb, t_escrita, pico_rss
        if not pendentes:
            return
        a = time.perf_counter()
        m = emb.embed_lote([t for t, _, _ in pendentes])
        b = time.perf_counter()
        fv.write(m.tobytes())
        linhas = []
        for t, doc_id, ordem in pendentes:
            dados = t.encode("utf-8")
            ft.write(dados)
            linhas.append((n_trechos, doc_id, ordem, offsets[-1], len(dados)))
            offsets.append(offsets[-1] + len(dados))
            n_trechos += 1
        con.executemany("INSERT INTO chunks VALUES (?,?,?,?,?)", linhas)
        pico_rss = max(pico_rss, metrics.status().get("VmRSS", 0))
        pendentes.clear()
        t_emb += b - a
        t_escrita += time.perf_counter() - b

    for doc_id, arq in enumerate(arquivos):
        a = time.perf_counter()
        try:
            with open(arq, "r", encoding="utf-8") as f:
                texto = f.read()
        except OSError as e:
            falhas += 1
            if logger:
                logger.log("falha_ingestao", arquivo=arq, erro=type(e).__name__, msg=str(e)[:120])
            continue
        t_leitura += time.perf_counter() - a
        bytes_corpus += len(texto.encode("utf-8"))
        linhas = texto.split("\n", 2)
        titulo = linhas[0]
        topico = linhas[1].replace("topico:", "").strip() if len(linhas) > 1 else ""
        con.execute("INSERT INTO docs VALUES (?,?,?,?,?)",
                    (doc_id, arq, titulo, topico, len(texto)))
        for ordem, tr in enumerate(fragmentar(texto, tamanho, sobreposicao)):
            pendentes.append((tr, doc_id, ordem))
        if len(pendentes) >= lote:
            descarregar()
    descarregar()
    con.commit()
    con.close()
    fv.close()
    ft.close()
    np.asarray(offsets, dtype=np.int64).tofile(p["offsets"])
    dt = time.perf_counter() - t0
    io1, ru1 = metrics.proc_io(), metrics.rusage()
    meta = {
        "dim": dim, "n_trechos": n_trechos, "n_docs": len(arquivos) - falhas,
        "falhas_leitura": falhas, "bytes_corpus": bytes_corpus,
        "bytes_vetores": os.path.getsize(p["vetores"]),
        "bytes_textos": os.path.getsize(p["textos"]),
        "bytes_offsets": os.path.getsize(p["offsets"]),
        "bytes_db": os.path.getsize(p["db"]),
        "tamanho_trecho": tamanho, "sobreposicao": sobreposicao, "lote": lote,
    }
    with open(p["meta"], "w") as f:
        json.dump(meta, f, indent=2)
    io = metrics.delta(io0, io1)
    ru = metrics.delta(ru0, ru1)
    resumo = dict(meta)
    resumo.update({"t_total_s": dt, "t_leitura_s": t_leitura, "t_embedding_s": t_emb,
                   "t_escrita_s": t_escrita, "pico_rss_mb": pico_rss,
                   "maxrss_mb": ru1["maxrss_mb"], "minflt": ru["minflt"], "majflt": ru["majflt"],
                   "rchar": io.get("rchar", 0), "wchar": io.get("wchar", 0),
                   "read_bytes": io.get("read_bytes", 0), "write_bytes": io.get("write_bytes", 0),
                   "syscr": io.get("syscr", 0), "syscw": io.get("syscw", 0),
                   "trechos_por_s": n_trechos / dt if dt else 0})
    if logger:
        logger.log("ingestao_concluida", **{k: resumo[k] for k in
                                             ("n_docs", "n_trechos", "falhas_leitura", "t_total_s")})
    return resumo
