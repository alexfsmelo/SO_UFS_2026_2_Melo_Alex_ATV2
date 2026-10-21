"""C1 (leitura convencional) x C2 (mmap) e Parte E.

Para cada arquivo de vetores (S, M, L e XL sintetico), modo, padrao de acesso
e estado do cache de paginas (frio/quente), executa a sonda em processo novo.
"""
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import PY, RAIZ, REPS, Planilha, agora, descartar_caches, progresso  # noqa: E402

sys.path.insert(0, RAIZ)
from genresearch.metrics import descartar_cache_arquivo  # noqa: E402

XL_MB = int(os.environ.get("XL_MB", "1024"))


def garantir_xl():
    p = os.path.join(RAIZ, "index", "XL_vectors.f32")
    alvo = XL_MB * 1024 * 1024
    if os.path.exists(p) and os.path.getsize(p) == alvo:
        return p
    os.makedirs(os.path.dirname(p), exist_ok=True)
    rng = np.random.default_rng(5)
    linhas_bloco = 65536
    total_linhas = alvo // (256 * 4)
    with open(p, "wb") as f:
        feitas = 0
        while feitas < total_linhas:
            n = min(linhas_bloco, total_linhas - feitas)
            f.write(rng.standard_normal((n, 256), dtype=np.float32).tobytes())
            feitas += n
    return p


def main():
    arquivos = {
        "S": os.path.join(RAIZ, "index", "S", "vectors.f32"),
        "M": os.path.join(RAIZ, "index", "M", "vectors.f32"),
        "L": os.path.join(RAIZ, "index", "L", "vectors.f32"),
        "XL": garantir_xl(),
    }
    plan = Planilha("c1c2_io.csv")
    for nome, arq in arquivos.items():
        for acesso in ("varredura", "esparso"):
            for modo in ("read", "mmap"):
                for rep in range(1, REPS + 1):
                    for estado in ("frio", "quente"):
                        metodo = "-"
                        if estado == "frio":
                            metodo = descartar_caches()
                            descartar_cache_arquivo(arq)
                        cmd = [PY, "-m", "genresearch.ioprobe", arq, "--modo", modo,
                               "--acesso", acesso]
                        p = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True,
                                           timeout=300)
                        if p.returncode != 0:
                            progresso(f"falha sonda {nome} {modo}: {p.stderr[-300:]}")
                            continue
                        r = json.loads(p.stdout.strip().splitlines()[-1])
                        r.update({"corpus": nome, "estado_cache": estado, "rep": rep,
                                  "metodo_descarte": metodo, "horario": agora()})
                        plan.add(r)
                progresso(f"C1/C2 {nome} {acesso} {modo} ok")
    # variante de padrao de leitura: madvise no mmap (L, varredura, frio)
    for adv in ("willneed", "sequential", "random"):
        for rep in range(1, REPS + 1):
            descartar_caches()
            descartar_cache_arquivo(arquivos["L"])
            p = subprocess.run([PY, "-m", "genresearch.ioprobe", arquivos["L"], "--modo", "mmap",
                                "--acesso", "varredura", "--madvise", adv],
                               cwd=RAIZ, capture_output=True, text=True, timeout=300)
            r = json.loads(p.stdout.strip().splitlines()[-1])
            r.update({"corpus": "L", "estado_cache": "frio", "rep": rep, "horario": agora()})
            plan.add(r)
    progresso("C1/C2 madvise ok")


if __name__ == "__main__":
    main()
