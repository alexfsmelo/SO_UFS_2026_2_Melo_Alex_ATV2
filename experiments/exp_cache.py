"""C4: cache compartilhado. Cargas repetida, parafrase, distinta e mista;
tamanho 0, 8 e 64; politicas LRU e FIFO; modo lock e singleflight."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import REPS, Planilha, achatar, agora, progresso, rodar_serve  # noqa: E402

CONFIGS = [(0, "lru", "lock"), (8, "lru", "lock"), (8, "fifo", "lock"), (64, "lru", "lock"),
           (64, "fifo", "lock"), (64, "lru", "singleflight")]


def main():
    plan = Planilha("c4_cache.csv")
    for carga in ("repetida", "parafrase", "distinta", "mista"):
        for tam, pol, modo in CONFIGS:
            for rep in range(1, REPS + 1):
                rot = f"c4_{carga}_{tam}_{pol}_{modo}_r{rep}"
                cfg = {"indice": "index/M", "saida": "results/raw/c4", "rotulo": rot,
                       "trabalhadores": 2, "produtores": 2, "requisicoes": 150,
                       "capacidade_fila": 16, "timeout_put": 30.0, "carga": carga,
                       "cache_tam": tam, "cache_politica": pol, "cache_modo": modo,
                       "chegada_ms": 10.0, "seed": 200 + rep}
                cod, s, out, dt = rodar_serve(cfg)
                linha = {"carga": carga, "cache_tam": tam, "politica": pol, "modo": modo,
                         "rep": rep, "codigo": cod, "horario": agora()}
                if s:
                    linha.update(achatar(s))
                plan.add(linha)
            progresso(f"C4 {carga} {tam} {pol} {modo} ok")


if __name__ == "__main__":
    main()
