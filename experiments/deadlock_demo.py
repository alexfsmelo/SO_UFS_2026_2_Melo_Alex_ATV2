"""Demonstracao isolada de espera circular entre dois recursos do servidor
(trava do indice e trava do cache).

modo ingenuo:  T1 pega indice -> cache; T2 pega cache -> indice. Deadlock.
               O processo so termina porque o processo pai aplica timeout e o mata.
modo timeout:  acquire(timeout); ao falhar, libera o que tem, espera aleatoria e tenta de novo
               (deteccao + recuperacao).
modo ordenado: ambos adquirem na mesma ordem global (prevencao: quebra a espera circular).
Imprime JSON com o resultado.
"""
import json
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from genresearch.metrics import nomear_thread  # noqa: E402

trava_indice = threading.Lock()
trava_cache = threading.Lock()
ITER = 200
estado = {"concluidas": [0, 0], "retentativas": [0, 0]}


def tarefa(tid, primeira, segunda, modo):
    nomear_thread(f"dl-t{tid}")
    rng = random.Random(tid)
    for _ in range(ITER):
        if modo == "timeout":
            while True:
                with primeira:
                    time.sleep(0.0005)
                    if segunda.acquire(timeout=0.01):
                        try:
                            estado["concluidas"][tid] += 1
                        finally:
                            segunda.release()
                        break
                estado["retentativas"][tid] += 1
                time.sleep(rng.uniform(0, 0.002))
        else:
            with primeira:
                time.sleep(0.0005)  # aumenta a chance de intercalacao
                with segunda:
                    estado["concluidas"][tid] += 1


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "ingenuo"
    print(json.dumps({"pid": os.getpid(), "modo": modo}), flush=True)
    if modo == "ordenado":
        pares = [(trava_indice, trava_cache), (trava_indice, trava_cache)]
    else:
        pares = [(trava_indice, trava_cache), (trava_cache, trava_indice)]
    t0 = time.perf_counter()
    ts = [threading.Thread(target=tarefa, args=(i, *pares[i], modo)) for i in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(json.dumps({"modo": modo, "tempo_s": time.perf_counter() - t0,
                      "concluidas": estado["concluidas"],
                      "retentativas": estado["retentativas"]}), flush=True)


if __name__ == "__main__":
    main()
