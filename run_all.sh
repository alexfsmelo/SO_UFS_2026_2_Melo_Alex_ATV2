#!/usr/bin/env bash
# Reproduz todos os experimentos da AV2. Requer Linux, Python >= 3.10, numpy e matplotlib.
# Partes que usam drop_caches, cgroup e swap (C1/C2 frio, C5c, C6 memoria) precisam de root;
# sem root, o cache frio usa posix_fadvise e os casos de cgroup sao pulados com aviso.
# Uso: sudo -E ./run_all.sh          (completo, ~25 min)
#      REPS=1 ./run_all.sh rapido     (demonstracao curta, sem C5c)
set -u
cd "$(dirname "$0")"
MODO=${1:-completo}
mkdir -p results/{raw,tables,figures,logs,evidence}

echo "== Parte A: ambiente"; bash experiments/ambiente.sh

echo "== corpus e ingestao (S, M, L)"
for c in S:500 M:5000 L:40000; do
  n=${c%%:*}; d=${c##*:}
  [ -d data/$n/docs ] || python3 -m genresearch corpus --docs $d --saida data/$n
  [ -f index/$n/meta.json ] || python3 -m genresearch ingest --corpus data/$n --indice index/$n --json results/raw/ingest_$n.json >/dev/null
done

echo "== C1/C2: read x mmap";            python3 experiments/exp_io.py          | tee results/logs/exp_io.out
echo "== C3: concorrencia e fila";       python3 experiments/exp_concorrencia.py | tee results/logs/exp_c3.out
echo "== C4: cache compartilhado";       python3 experiments/exp_cache.py       | tee results/logs/exp_c4.out
if [ "$MODO" = "rapido" ]; then
  echo "== C5: pressao de memoria (a, b)"; python3 experiments/exp_memoria.py a b | tee results/logs/exp_c5.out
else
  echo "== C5: pressao de memoria";       python3 experiments/exp_memoria.py     | tee results/logs/exp_c5.out
fi
echo "== C6: falhas controladas";        python3 experiments/exp_falhas.py      | tee results/logs/exp_c6.out
echo "== D: sincronizacao";              python3 experiments/exp_sync.py        | tee results/logs/exp_d.out
echo "== evidencias";                    bash experiments/evidencias.sh
echo "== tabelas e graficos";            python3 experiments/analise.py
echo "concluido: results/"
