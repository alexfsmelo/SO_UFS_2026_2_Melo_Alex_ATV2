# -*- coding: utf-8 -*-
# Relacao com SO e IA generativa, limitacoes, conclusao, referencias e anexos.

h1("12. Relação com Sistemas Operacionais e IA generativa")
bl(f"**Pesos e índices são arquivos mapeados.** Runtimes como llama.cpp (base do Ollama) carregam pesos GGUF com `mmap`: o modelo \"carrega\" em milissegundos e as páginas entram sob demanda, exatamente como `vectors.f32` no C2. A diferença entre a primeira e a segunda execução da AV1 é o cache de páginas: na segunda, os pesos já estavam em RAM.",
   "**RSS de arquivo x anônima decide quem sobrevive à pressão.** Pesos mapeados e índices somente leitura podem ser descartados e relidos (C5c com mmap sob limite); buffers anônimos, KV-cache e tensores intermediários não, e terminam em swap ou OOM (read sob 192 MB). Por isso servidores de LLM pré-alocam e limitam o KV-cache, e o vLLM o pagina em blocos fixos (PagedAttention), aplicando ao KV-cache a mesma ideia de paginação da memória virtual.",
   f"**Contexto e lote são memória.** Top-k maior aumentou bytes tocados, faltas de página e custo de prefill; o lote de 65.536 na ingestão multiplicou o pico de RSS por {f(b2.pico_rss_mb / b0.pico_rss_mb, 1)} em relação ao de 256, com ganho pequeno de vazão. Em LLMs, contexto e lote escalam o KV-cache e a ocupação de VRAM.",
   "**Checkpoints e embeddings em disco.** Gravar e reler checkpoints ou matrizes de embeddings é E/S sequencial grande: readahead ajuda, `MADV_RANDOM` destrói o desempenho, e o cache de páginas pode esconder o custo do disco em medições ingênuas (por isso as medidas frias com drop_caches).",
   "**Servir modelo é produtor/consumidor.** Requisições em fila limitada, workers, backpressure (rejeição com timeout), retentativa com recuo e cache de respostas (incluindo singleflight contra o efeito manada) são os mesmos mecanismos de servidores de inferência reais. O GIL do Python explica por que servidores de modelo fazem a computação pesada em C/C++ ou em processos separados.")

h1("13. Limitações")
bl("Embeddings por hashing e geração simulada preservam o padrão de memória e espera, mas não a computação de um modelo real; o custo de CPU/GPU de um transformer não foi medido aqui.",
   "Um único nó com 2 vCPUs, sem GPU e sem VRAM: não há transferência PCIe, paginação de VRAM, NCCL nem contenção entre GPUs; múltiplas GPUs e ambientes distribuídos acrescentam rede, sincronização entre nós e falhas parciais que este recorte não cobre.",
   "Disco virtual (virtio) em VM de nuvem: latências e vazão não equivalem a um NVMe local; o cache do hipervisor pode suavizar leituras \"frias\".",
   "Python com GIL limita a concorrência de CPU; os resultados de escalabilidade valem para cargas dominadas por espera de E/S.",
   "Busca vetorial exata por varredura; índices aproximados (HNSW, IVF) tocam muito menos memória por consulta e mudariam o perfil de faltas de página.",
   "Corpus sintético e cargas determinísticas; tráfego real tem distribuição de popularidade e de tamanhos diferente. Três repetições bastam para os efeitos grandes medidos, não para diferenças pequenas.",
   "Os experimentos foram executados na VM descrita na Seção 3, e não no notebook do discente; a reexecução é feita por `run_all.sh`.")

h1("14. Conclusão")
p("Respondendo à pergunta norteadora: **memória e armazenamento** definem o custo de ter o índice disponível, e a forma de leitura importa tanto quanto o tamanho. `read()` paga cópia e memória anônima proporcionais ao arquivo; `mmap()` paga faltas de página só no que é tocado e deixa o kernel administrar o resto como cache de páginas. Sob limite de memória, essa diferença separa degradação (mmap relendo do disco) de falha (OOM). **Filas e concorrência** aumentam a vazão quando a carga é dominada por espera e não quando é CPU sob o GIL; uma fila maior não cria capacidade, só converte bloqueio em latência. **Caches** economizam a maior parte do trabalho quando há repetição, nada quando não há, e exigem sincronização não só para não corromper a estrutura, mas também para não repetir trabalho. **Sincronização** é condição de correção: sem ela houve atualizações perdidas, logs corrompidos e cálculo duplicado; com ela, o custo foi pequeno nas regiões curtas e exigiu desenho (singleflight, ordem de travas, timeouts) nas longas.")

h1("15. Referências")
for ref in [
    "ARPACI-DUSSEAU, R. H.; ARPACI-DUSSEAU, A. C. _Operating Systems: Three Easy Pieces_. Arpaci-Dusseau Books, 2018. Disponível em: https://pages.cs.wisc.edu/~remzi/OSTEP/.",
    "SILBERSCHATZ, A.; GALVIN, P. B.; GAGNE, G. _Operating System Concepts_. 10. ed. Wiley, 2018.",
    "TANENBAUM, A. S.; BOS, H. _Modern Operating Systems_. 4. ed. Pearson, 2014.",
    "GREGG, B. _Systems Performance: Enterprise and the Cloud_. 2. ed. Addison-Wesley, 2020.",
    "THE LINUX KERNEL. The /proc filesystem; Memory Resource Controller (cgroup v1). Disponível em: https://docs.kernel.org/filesystems/proc.html e https://docs.kernel.org/admin-guide/cgroup-v1/memory.html.",
    "LINUX MAN-PAGES PROJECT. mmap(2), madvise(2), mincore(2), posix_fadvise(2), read(2), write(2), getrusage(2), prctl(2), proc(5). Disponível em: https://man7.org/linux/man-pages/.",
    "PYTHON SOFTWARE FOUNDATION. threading, mmap e sqlite3. _Python 3 Documentation_. Disponível em: https://docs.python.org/3/library/.",
    "LEWIS, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. In: _NeurIPS_, 2020.",
    "KWON, W. et al. Efficient Memory Management for Large Language Model Serving with PagedAttention. In: _SOSP_, 2023.",
    "WEINBERGER, K. et al. Feature Hashing for Large Scale Multitask Learning. In: _ICML_, 2009.",
    "GGML-ORG. llama.cpp. Disponível em: https://github.com/ggml-org/llama.cpp. OLLAMA. Disponível em: https://github.com/ollama/ollama.",
]:
    B.append({"p": ref})

h1("Anexo A. Evidências do sistema operacional")
p("Trechos de `results/evidence/` (arquivos completos no repositório).")
for nome, titulo, n in (("processo_vivo.txt", "Processo em execução: threads, memória e mapeamentos (corpus L, 4 trabalhadores)", 34),
                        ("strace_resumo_servidor.txt", "strace -f -c de uma execução completa do servidor (M, 4 trabalhadores, 80 requisições)", 18),
                        ("strace_read_L_resumo.txt", "strace -e: read() sobre vectors.f32 (L)", 12),
                        ("strace_mmap_L_resumo.txt", "strace -e: mmap() sobre vectors.f32 (L)", 12)):
    caminho = os.path.join(RAIZ, "results", "evidence", nome)
    if os.path.exists(caminho):
        linhas_ev = [l.rstrip()[:118] for l in open(caminho, encoding="utf-8", errors="replace")]
        if nome == "processo_vivo.txt":
            sel = [l for l in linhas_ev if l.strip()][:n]
        else:
            sel = linhas_ev[:n]
        h2(titulo)
        B.append({"code": "\n".join(sel)})
if N.get("deadlock_threads"):
    h2("Deadlock ingênuo: estado das threads no momento do timeout")
    B.append({"code": N["deadlock_threads"].replace(" ; ", "\n")})
if N.get("log_exemplo"):
    h2("Exemplo de linha de log corrompida (modo sem mutex)")
    B.append({"code": N["log_exemplo"]})
fig("f4_c3_serie.png", "Figura A1. Série temporal de uma execução do C3 (E/S, fila 64, 2 trabalhadores): a fila enche na rajada e é drenada a taxa constante.", 14)
