"""Funcoes compartilhadas pelos scripts de experimento."""
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(RAIZ, "results", "raw")
PY = sys.executable
REPS = int(os.environ.get("REPS", "3"))


def agora():
    return datetime.now().isoformat(timespec="seconds")


def caminho_cgroup_v1():
    try:
        with open("/proc/self/cgroup") as f:
            for linha in f:
                partes = linha.strip().split(":")
                if len(partes) == 3 and partes[1] == "memory":
                    base = "/sys/fs/cgroup/memory" + partes[2]
                    return base if os.path.isdir(base) else None
    except OSError:
        pass
    return None


def caminho_cgroup_v2():
    if not os.path.exists("/sys/fs/cgroup/cgroup.controllers"):
        return None
    with open("/sys/fs/cgroup/cgroup.controllers") as f:
        if "memory" not in f.read().split():
            return None
    with open("/proc/self/cgroup") as f:
        for linha in f:
            if linha.startswith("0::"):
                return "/sys/fs/cgroup" + linha.strip()[3:]
    return None


class CgroupMemoria:
    """Cria um cgroup filho com limite de memoria (v1 ou v2). Requer root."""

    def __init__(self, nome, limite_mb, swap=True):
        self.ok = False
        self.versao = None
        self.limite_mb = limite_mb
        base = caminho_cgroup_v1()
        try:
            if base:
                self.path = os.path.join(base, nome)
                os.makedirs(self.path, exist_ok=True)
                self._w("memory.limit_in_bytes", str(limite_mb * 1024 * 1024))
                if not swap:
                    try:
                        self._w("memory.memsw.limit_in_bytes", str(limite_mb * 1024 * 1024))
                    except OSError:
                        self._w("memory.swappiness", "0")
                self.versao = 1
                self.ok = True
                return
            base = caminho_cgroup_v2()
            if base:
                self.path = os.path.join(base, nome)
                os.makedirs(self.path, exist_ok=True)
                self._w("memory.max", str(limite_mb * 1024 * 1024))
                if not swap:
                    self._w("memory.swap.max", "0")
                self.versao = 2
                self.ok = True
        except OSError as e:
            self.erro = str(e)
            self.ok = False

    def _w(self, arq, valor):
        with open(os.path.join(self.path, arq), "w") as f:
            f.write(valor)

    def preexec(self):
        path = self.path

        def _f():
            with open(os.path.join(path, "cgroup.procs"), "w") as f:
                f.write(str(os.getpid()))
        return _f

    def estatisticas(self):
        out = {}
        try:
            if self.versao == 1:
                for k in ("memory.failcnt", "memory.max_usage_in_bytes", "memory.memsw.max_usage_in_bytes"):
                    p = os.path.join(self.path, k)
                    if os.path.exists(p):
                        out[k] = int(open(p).read())
                for linha in open(os.path.join(self.path, "memory.oom_control")):
                    k, v = linha.split()
                    out["oom_" + k] = int(v)
            else:
                for linha in open(os.path.join(self.path, "memory.events")):
                    k, v = linha.split()
                    out["ev_" + k] = int(v)
                out["memory.peak"] = int(open(os.path.join(self.path, "memory.peak")).read())
        except OSError:
            pass
        return out

    def remover(self):
        try:
            os.rmdir(self.path)
        except OSError:
            pass


def opcoes(cfg):
    args = []
    for k, v in cfg.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    return args


def rodar_serve(cfg, timeout=600, preexec=None, extra=()):
    """Executa uma rodada do servidor em processo novo. Retorna (codigo, resumo|None, saida)."""
    cmd = [PY, "-m", "genresearch", "serve", "--quiet"] + opcoes(cfg) + list(extra)
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=timeout,
                           preexec_fn=preexec)
        codigo = p.returncode
        saida = (p.stdout + p.stderr)[-2000:]
    except subprocess.TimeoutExpired as e:
        codigo = "timeout"
        saida = str(e)[-500:]
    dt = time.perf_counter() - t0
    resumo = None
    arq = os.path.join(RAIZ, cfg["saida"], cfg["rotulo"] + ".summary.json")
    if codigo == 0 and os.path.exists(arq):
        with open(arq) as f:
            resumo = json.load(f)
    return codigo, resumo, saida, dt


def achatar(s, prefixo=""):
    out = {}
    for k, v in s.items():
        if k == "config":
            continue
        chave = f"{prefixo}{k}"
        if isinstance(v, dict):
            out.update(achatar(v, chave + "."))
        else:
            out[chave] = v
    return out


class Planilha:
    """Acumula linhas e grava CSV (colunas = uniao das chaves)."""

    def __init__(self, nome):
        self.caminho = os.path.join(RAW, nome)
        self.linhas = []

    def add(self, linha):
        self.linhas.append(linha)
        self.salvar()

    def salvar(self):
        os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
        cols = []
        for l in self.linhas:
            for k in l:
                if k not in cols:
                    cols.append(k)
        with open(self.caminho, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for l in self.linhas:
                w.writerow(l)


def descartar_caches():
    try:
        os.sync()
        with open("/proc/sys/vm/drop_caches", "w") as f:
            f.write("3\n")
        return "drop_caches"
    except OSError:
        return "fadvise"


def progresso(msg):
    print(f"[{agora()}] {msg}", flush=True)
