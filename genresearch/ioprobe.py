"""Sonda de E/S para C1 (read) x C2 (mmap). Executada em processo separado
para que RSS, faltas de pagina e contadores de E/S sejam isolados.

Uso: python -m genresearch.ioprobe ARQUIVO --modo read|mmap --acesso varredura|esparso
Imprime uma linha JSON com as medidas.
"""
import argparse
import json
import mmap
import os
import time

import numpy as np

from . import metrics


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo")
    ap.add_argument("--modo", choices=["read", "mmap"], required=True)
    ap.add_argument("--acesso", choices=["varredura", "esparso"], default="varredura")
    ap.add_argument("--dim", type=int, default=256)
    ap.add_argument("--linhas-esparso", type=int, default=256)
    ap.add_argument("--madvise", choices=["nenhum", "willneed", "random", "sequential"],
                    default="nenhum")
    a = ap.parse_args(argv)

    tam = os.path.getsize(a.arquivo)
    n = tam // (4 * a.dim)
    res_antes = metrics.residencia_cache(a.arquivo)[0]
    st0, ru0, io0 = metrics.status(), metrics.rusage(), metrics.proc_io()
    t0 = time.perf_counter()
    f = open(a.arquivo, "rb")
    t_open = time.perf_counter() - t0
    mm = None
    if a.modo == "read":
        buf = f.read()
    else:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        if a.madvise != "nenhum":
            mm.madvise({"willneed": mmap.MADV_WILLNEED, "random": mmap.MADV_RANDOM,
                        "sequential": mmap.MADV_SEQUENTIAL}[a.madvise])
        buf = mm
    M = np.frombuffer(buf, dtype=np.float32, count=n * a.dim).reshape(n, a.dim)
    t_carga = time.perf_counter() - t0
    st1, ru1 = metrics.status(), metrics.rusage()

    rng = np.random.default_rng(3)
    q = rng.standard_normal(a.dim).astype(np.float32)
    linhas = rng.choice(n, size=min(a.linhas_esparso, n), replace=False)

    def acessar():
        if a.acesso == "varredura":
            s = M @ q
            return float(s.max())
        return float(M[np.sort(linhas)].sum())

    t1 = time.perf_counter()
    acessar()
    t_acesso1 = time.perf_counter() - t1
    st2, ru2, io2 = metrics.status(), metrics.rusage(), metrics.proc_io()
    t2 = time.perf_counter()
    acessar()
    t_acesso2 = time.perf_counter() - t2
    ru3 = metrics.rusage()
    res_depois = metrics.residencia_cache(a.arquivo)[0]
    out = {
        "arquivo": os.path.basename(a.arquivo), "bytes": tam, "linhas": n, "modo": a.modo,
        "acesso": a.acesso, "madvise": a.madvise,
        "t_open_s": t_open, "t_carga_s": t_carga, "t_acesso1_s": t_acesso1,
        "t_acesso2_s": t_acesso2, "t_total_s": t_carga + t_acesso1,
        "rss_base_mb": st0.get("VmRSS"), "rss_apos_carga_mb": st1.get("VmRSS"),
        "rss_apos_acesso_mb": st2.get("VmRSS"), "rss_anon_mb": st2.get("RssAnon"),
        "rss_file_mb": st2.get("RssFile"), "vsz_mb": st2.get("VmSize"),
        "delta_rss_mb": st2.get("VmRSS", 0) - st0.get("VmRSS", 0),
        "delta_vsz_mb": st2.get("VmSize", 0) - st0.get("VmSize", 0),
        "minflt_carga": ru1["minflt"] - ru0["minflt"], "majflt_carga": ru1["majflt"] - ru0["majflt"],
        "minflt_acesso1": ru2["minflt"] - ru1["minflt"], "majflt_acesso1": ru2["majflt"] - ru1["majflt"],
        "minflt_acesso2": ru3["minflt"] - ru2["minflt"], "majflt_acesso2": ru3["majflt"] - ru2["majflt"],
        "rchar": io2.get("rchar", 0) - io0.get("rchar", 0),
        "read_bytes": io2.get("read_bytes", 0) - io0.get("read_bytes", 0),
        "syscr": io2.get("syscr", 0) - io0.get("syscr", 0),
        "residencia_antes": res_antes, "residencia_depois": res_depois,
    }
    print(json.dumps(out))
    del M
    buf = None
    if mm is not None:
        mm.close()
    f.close()


if __name__ == "__main__":
    main()
