# AV2 · GenResearch-Servidor

**Sistemas Operacionais (COMP0472) · UFS · 2026.2**
Memória, armazenamento, sincronização e desempenho de aplicações de IA generativa

**Discente:** Álex Felipe Santos Melo (202200025395)
**Professor:** Glauco de Figueiredo Carneiro
**Modalidade:** individual

## Entregáveis

* Relatório: [docs/relatorio_AV2_SO_Alex_Melo.pdf](docs/relatorio_AV2_SO_Alex_Melo.pdf)
* Slides: [docs/slides_AV2_SO_Alex_Melo.pdf](docs/slides_AV2_SO_Alex_Melo.pdf)
* Vídeo: PREENCHER_URL_DO_VIDEO (também em [VIDEO.md](VIDEO.md))
* Contribuição individual: [CONTRIBUICAO.md](CONTRIBUICAO.md)
* Declaração de uso de IA: [DECLARACAO_IA.md](DECLARACAO_IA.md)

## O que é

Um serviço simplificado de RAG, em Python, feito para ser **observável pelo sistema operacional**. Ele não tenta gerar boas respostas: tenta mostrar como RAM, memória virtual, cache de páginas, disco, filas, threads, cache de respostas e travas se comportam numa carga inspirada em IA generativa.

```
 produtores (threads) ──put──▶ [ buffer limitado: semáforos empty/full + mutex ] ──get──▶ trabalhadores (threads)
                                                                                         │
             ┌───────────────────────────────────────────────────────────────────────────┤
             ▼                                                                           ▼
   cache compartilhado (LRU/FIFO,                                   embedding da consulta (hashing, 256 dim)
   mutex ou singleflight)                                           busca no índice (vectors.f32 via read() ou mmap())
             ▲                                                      contexto limitado (texts.bin + offsets + SQLite)
             └──────────── resposta ◀── gerador (simulado: espera de E/S; ou Ollama local)
   log JSONL protegido por mutex · amostrador de /proc (RSS, VSZ, faltas de página, fila, ocupação)
```

| Componente | Arquivo | Mecanismo de SO observado |
|---|---|---|
| Corpus sintético | `genresearch/corpus.py` | escrita de arquivos |
| Ingestão e embeddings | `genresearch/ingest.py`, `embed.py` | E/S sequencial, lote e pico de RSS |
| Índice | `genresearch/store.py` | `read()` x `mmap()`, cache de páginas, SQLite |
| Fila | `genresearch/bbuffer.py` | semáforos `empty`/`full` + mutex, timeout |
| Cache | `genresearch/cache.py` | condição de corrida, mutex, singleflight |
| Log | `genresearch/logger.py` | `write()` com `O_APPEND`, intercalação |
| Geração | `genresearch/generator.py` | espera bloqueante (E/S) x CPU com GIL |
| Métricas | `genresearch/metrics.py` | `/proc/self/status`, `/proc/self/io`, `getrusage`, `mincore` |

## Requisitos

* Linux (nativo, VM, WSL2 ou contêiner). Os resultados do relatório foram obtidos em VM Linux (KVM), Ubuntu 24.04.5, kernel 6.18, 2 vCPUs, 7,8 GiB; detalhes em `results/evidence/ambiente.txt`.
* Python 3.10 ou superior
* `pip install -r requirements.txt` (numpy, matplotlib, pandas, tabulate)
* Opcional: `strace`, `sysstat` (iostat, pidstat), Ollama
* **Root** para: descarte global do cache de páginas (`drop_caches`), cgroups de memória (C5c e C6) e arquivo de swap temporário. Sem root, o cache frio usa `posix_fadvise(DONTNEED)` e os casos de cgroup são pulados com aviso.

## Execução rápida

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 -m genresearch corpus --docs 5000 --saida data/M
python3 -m genresearch ingest --corpus data/M --indice index/M
python3 -m genresearch serve  --indice index/M --saida results/raw/demo --rotulo demo \
        --trabalhadores 4 --produtores 2 --requisicoes 120 --cache-tam 32 --carga mista
cat results/raw/demo/demo.summary.json
```

Todas as opções do servidor: `python3 -m genresearch serve -h`. Exemplos úteis:

```bash
# leitura convencional em vez de mmap
... serve --modo-io read
# carga limitada por CPU (Python puro, segura o GIL)
... serve --prefill-tps 0 --decode-tps 0 --cpu-ms 40
# falha controlada do cache (sem mutex) e do log (sem mutex, gravação fragmentada)
... serve --cache-tam 64 --cache-modo none --log-modo unsafe --carga repetida
# geração real com Ollama local
... serve --backend ollama --modelo-ollama deepseek-r1:1.5b --requisicoes 10 --trabalhadores 1
```

## Reprodução completa dos experimentos

```bash
sudo -E env PATH=$PATH ./run_all.sh          # tudo, cerca de 25 minutos
REPS=1 ./run_all.sh rapido                  # versão curta para demonstração
```

O script gera o corpus (S, M, L), executa a Parte A, C1 a C6, a Parte D, as evidências e, por fim, `experiments/analise.py`, que produz as tabelas e os gráficos.

| Experimento | Script | Saída bruta |
|---|---|---|
| Parte A (ambiente) | `experiments/ambiente.sh` | `results/evidence/ambiente.txt` |
| C1 leitura convencional, C2 mmap, Parte E | `experiments/exp_io.py` | `results/raw/c1c2_io.csv` |
| C3 concorrência e fila | `experiments/exp_concorrencia.py` | `results/raw/c3_concorrencia.csv`, `results/raw/c3/` |
| C4 cache compartilhado | `experiments/exp_cache.py` | `results/raw/c4_cache.csv`, `results/raw/c4/` |
| C5 pressão de memória | `experiments/exp_memoria.py` | `results/raw/c5a_*.csv`, `c5b_*.csv`, `c5c_*.csv` |
| C6 falhas controladas | `experiments/exp_falhas.py` | `results/raw/c6_falhas.csv`, `results/raw/c6/` |
| Parte D sincronização | `experiments/exp_sync.py`, `deadlock_demo.py` | `results/raw/d_*.csv` |
| Evidências (strace, /proc, ps -L, iostat, vmstat) | `experiments/evidencias.sh` | `results/evidence/` |
| Tabelas e gráficos | `experiments/analise.py` | `results/tables/`, `results/figures/` |

Cada execução do servidor grava, com o mesmo rótulo: `*.summary.json` (métricas agregadas e configuração), `*.requests.csv` (uma linha por requisição), `*.timeseries.csv` (amostras de fila, ocupação e memória a cada 50 ms) e `*.log.jsonl` (eventos).

## Validação

```bash
python3 experiments/validar.py
```

Confere estrutura e entregáveis, ausência de `.env` e de arquivos grandes, três repetições por configuração, médias das tabelas recalculadas a partir dos CSVs brutos, números do relatório recalculados e encontrados no PDF (requer `pdftotext`), invariantes de correção em todas as execuções com mutex (0 perdidas, 0 duplicadas, 0 linhas de log inválidas), evidências de SO e campos pendentes. Termina com código 1 se houver falha.

## Estrutura

```
SO_UFS_2026_2_Melo_Alex_ATV2/
├── genresearch/            código do servidor
├── experiments/            scripts de experimento, evidências e análise
├── results/
│   ├── raw/                CSVs e JSONs brutos de todas as repetições
│   ├── tables/             tabelas agregadas (Markdown e CSV)
│   ├── figures/            gráficos usados no relatório
│   ├── evidence/           ambiente, strace, /proc, ps -L, iostat, vmstat
│   └── logs/               saída dos scripts
├── docs/                   relatório (PDF e DOCX), slides (PDF), roteiro e comandos do vídeo
├── run_all.sh
├── requirements.txt
├── VIDEO.md
├── CONTRIBUICAO.md
└── DECLARACAO_IA.md
```

`data/` e `index/` não vão para o repositório (`.gitignore`): são regenerados de forma determinística (semente fixa) pelos comandos acima.

## Dados

Todo o corpus é **sintético**, gerado por `genresearch/corpus.py` com semente 42: documentos em português com termos de dez tópicos de SO e IA. Não há dados pessoais, chaves, tokens, `.env` nem pesos de modelo no repositório.

## Licença

Uso acadêmico, COMP0472/UFS 2026.2.
