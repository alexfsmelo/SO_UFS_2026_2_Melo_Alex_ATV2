"""C3: concorrencia e fila. 2 produtores; 1, 2 e 4 trabalhadores (threads);
capacidade da fila 4 e 64; carga limitada por E/S (espera do servico de
inferencia) e por CPU (Python puro, segura o GIL). Cache desligado."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import REPS, Planilha, achatar, agora, progresso, rodar_serve  # noqa: E402

CARGAS = {
    "es": {"prefill_tps": 20000.0, "decode_tps": 400.0, "cpu_ms": 0.0},
    "cpu": {"prefill_tps": 0.0, "decode_tps": 0.0, "cpu_ms": 40.0},
}


def main():
    plan = Planilha("c3_concorrencia.csv")
    for carga, gen in CARGAS.items():
        for cap in (4, 64):
            for w in (1, 2, 4):
                for rep in range(1, REPS + 1):
                    rot = f"c3_{carga}_cap{cap}_w{w}_r{rep}"
                    cfg = {"indice": "index/M", "saida": "results/raw/c3", "rotulo": rot,
                           "trabalhadores": w, "produtores": 2, "requisicoes": 120,
                           "capacidade_fila": cap, "timeout_put": 30.0, "carga": "distinta",
                           "cache_tam": 0, "modo_io": "mmap", "seed": 100 + rep}
                    cfg.update(gen)
                    cod, s, out, dt = rodar_serve(cfg)
                    linha = {"carga_tipo": carga, "capacidade": cap, "trabalhadores": w,
                             "rep": rep, "codigo": cod, "horario": agora()}
                    if s:
                        linha.update(achatar(s))
                    plan.add(linha)
                progresso(f"C3 {carga} cap={cap} w={w} ok")


if __name__ == "__main__":
    main()
