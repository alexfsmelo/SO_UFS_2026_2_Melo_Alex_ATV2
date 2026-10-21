# -*- coding: utf-8 -*-
# Secoes do relatorio. Executado por conteudo.py (tem acesso a N, t, f, i, pct, h1, h2, p, bl, fig, tab).

corp = {c["corpus"]: c for c in N["corpus"]}

B.append({"titulo": "GenResearch-Servidor: memória, armazenamento, sincronização e desempenho de uma aplicação de RAG"})
B.append({"subtitulo": "Sistemas Operacionais (COMP0472) · UFS · 2026.2 · Atividade 2 (AV2), individual"})
B.append({"subtitulo": "**Discente:** Álex Felipe Santos Melo (202200025395) · **Professor:** Glauco de Figueiredo Carneiro"})
B.append({"subtitulo": f"**Repositório:** {REPO} · **Vídeo:** {VIDEO} · Entrega: 20/10/2026"})

h1("1. Tabela de contribuição individual")
tab(["Integrante", "Matrícula", "Atividades", "Participação"],
    [["Álex Felipe Santos Melo", "202200025395",
      "Recorte experimental, arquitetura e implementação do servidor, execução de C1 a C6 e da Parte D, coleta de evidências, análise, relatório, slides e vídeo",
      "100%"]],
    "Tabela 1. Contribuição. O uso de IA generativa está descrito em DECLARACAO_IA.md no repositório.",
    pesos=[2.2, 1.3, 6, 1.2], esquerda=(2,))

h1("2. Introdução, problema e pergunta norteadora")
p("Aplicações de IA generativa com recuperação aumentada (RAG) parecem, vistas de fora, um problema de modelo. Vistas de dentro, são um problema de sistema operacional: documentos são lidos do disco, fragmentados, convertidos em vetores e gravados em arquivos e bancos; consultas chegam em rajadas e esperam em filas; um índice de centenas de megabytes precisa estar acessível a várias threads; respostas recentes vão para um cache compartilhado; tudo é registrado em log. Cada uma dessas etapas disputa RAM, cache de páginas, espaço de endereçamento, disco e travas.")
p("Este trabalho implementa e mede o **GenResearch-Servidor**, um serviço de RAG simplificado escrito em Python e desenhado para ser observável pelo sistema operacional. O foco não é a qualidade da resposta, e sim os custos que surgem durante a execução: quanto de memória cada forma de leitura consome, quando a concorrência ajuda e quando só cria fila, quanto o cache economiza e o que quebra quando um recurso compartilhado fica sem proteção.")
p("**Pergunta norteadora:** como memória principal, memória virtual, armazenamento, caches, filas compartilhadas e mecanismos de sincronização afetam o desempenho, a estabilidade e a correção de uma aplicação de IA generativa ou de RAG?")
p("**Recorte experimental.** Optou-se por corpus sintético em três tamanhos (S, M e L) mais um arquivo de vetores de 1 GB (XL) para a Parte E, embeddings simulados por _feature hashing_ (vetores reais em float32, sem modelo neural) e geração simulada como espera de um servidor de inferência, calibrada em tokens por segundo. Essa escolha mantém o padrão de acesso à memória e ao disco de um RAG real e torna os experimentos repetíveis em minutos. A integração com Ollama está implementada (`--backend ollama`), mas não foi usada nas medições, porque o tempo de geração real (dezenas de segundos por resposta na AV1) esconderia os efeitos de memória e sincronização que se quer observar.")

h1("3. Ambiente (Parte A)")
tab(["Item", "Valor"],
    [["Execução", "Máquina virtual Linux leve (KVM, kernel 6.18.44-fc), isolada, sem GUI; systemd-detect-virt reporta contêiner (docker) e /proc/cpuinfo traz a flag hypervisor"],
     ["Sistema operacional", "Ubuntu 24.04.5 LTS, kernel 6.18.44, x86_64, PREEMPT_DYNAMIC"],
     ["Processador", "Intel Xeon @ 2,10 GHz, 2 vCPUs (1 thread por núcleo), L2 4 MiB, L3 260 MiB"],
     ["Memória", "7,8 GiB (MemTotal 8.222.320 kB); MemAvailable 7.717.048 kB na coleta; páginas de 4 KiB"],
     ["Swap", "Nenhum fixo (SwapTotal 0); arquivo de swap de 2 GB criado só durante o C5c; vm.swappiness = 60"],
     ["Armazenamento", "Disco virtio /dev/vda, 256 GB, ext4 (relatime, discard)"],
     ["GPU", "Não há; toda a computação em CPU"],
     ["Software", "Python 3.13.16, NumPy 2.5.3, SQLite 3.45.1, matplotlib 3.11, strace, sysstat (iostat, pidstat), vmstat"],
     ["Modelo", "Sem modelo neural nas medições: embeddings por hashing (256 dimensões) e geração simulada; Ollama opcional"],
     ["Execução", "20/10/2026; commit registrado no repositório; detalhes brutos em results/evidence/ambiente.txt"]],
    "Tabela 2. Ambiente experimental (coletado por experiments/ambiente.sh: uname, os-release, lscpu, free, meminfo, lsblk, df, swapon, vmstat, iostat).",
    pesos=[2, 8], esquerda=(1,))
p("**MemFree, MemAvailable, cache e swap.** _MemFree_ é a RAM que não está sendo usada para nada. _MemAvailable_ é a estimativa do kernel de quanto pode ser entregue a novos processos sem recorrer a swap: soma a memória livre com a parte do cache de páginas e de estruturas do kernel que pode ser descartada. _Cached_ é o cache de páginas, cópias de blocos de arquivos mantidas em RAM. _Swap_ é a área em disco para onde vão páginas anônimas (heap, pilha, buffers do processo) quando falta RAM. Na coleta, MemFree e MemAvailable diferem em cerca de 224 MB justamente por causa do cache.")
p("**Cache de páginas não é desperdício.** Uma página de arquivo limpa em cache pode ser descartada a qualquer momento sem escrita em disco; mantê-la custa quase nada e evita uma leitura futura. Por isso uma máquina \"com pouca memória livre\" pode estar saudável: o que importa é MemAvailable e, sob pressão, a taxa de faltas de página maiores e de swap. Para RAG isso é central: datasets, índices vetoriais, embeddings e checkpoints de modelo são arquivos grandes, lidos repetidamente. Se cabem no cache de páginas, a segunda carga é muito mais rápida que a primeira (o efeito de \"aquecimento\" da AV1, quando o primeiro TTFT foi bem maior que os seguintes); se não cabem, cada acesso volta ao disco. Com `mmap`, o arquivo é paginado sob demanda e o mesmo quadro físico serve ao cache e ao processo.")

h1("4. Arquitetura")
fig("f0_arquitetura.png", "Figura 1. Arquitetura do GenResearch-Servidor: um processo, threads nomeadas no kernel (prctl), fila limitada, cache compartilhado, índice em arquivos e log.", 17)
p("Um único processo Python executa produtores e trabalhadores como threads. Os **produtores** geram consultas (carga determinística, semente fixa) e as colocam num **buffer limitado** implementado à mão com dois semáforos e um mutex. Os **trabalhadores** retiram requisições, calculam a chave normalizada da consulta e consultam o **cache compartilhado**. Em caso de erro de cache, fazem o embedding da consulta, varrem a matriz de vetores (produto M·q no NumPy, que libera o GIL), escolhem os top-k, montam um contexto limitado em tokens a partir de `texts.bin` e dos metadados no SQLite e chamam o **gerador**. Um **amostrador** lê /proc a cada 50 ms (fila, trabalhadores ocupados, RSS, VSZ, RssAnon, RssFile, swap, faltas de página, MemAvailable). Cada evento vai para um **log JSONL**. Cada execução grava resumo, uma linha por requisição, série temporal e log.")
p("**Por que threads.** A etapa dominante é a geração, que num RAG real é uma chamada HTTP bloqueante a um servidor de inferência (como o Ollama da AV1): a thread dorme esperando E/S e libera o GIL. A recuperação é NumPy, que também libera o GIL na multiplicação. Threads permitem compartilhar o índice mapeado e o cache sem cópia nem serialização. Para mostrar o limite dessa escolha, o C3 inclui uma carga limitada por CPU em Python puro, na qual o GIL impede o paralelismo.")

h1("5. Dados, corpus, embeddings, índice e cache")
linhas = []
for c in ("S", "M", "L"):
    d = corp[c]
    linhas.append([c, i(d["documentos"]), i(d["trechos"]), f(d["corpus_MB"], 1), f(d["vetores_MB"], 1),
                   f(d["textos_MB"], 1), f(d["sqlite_MB"], 1), f(d["ingestao_s"], 2), i(d["trechos_por_s"]),
                   f(d["pico_rss_MB"], 0)])
linhas.append(["XL", "-", "1.048.576", "-", f(N.get("xl_mb", 1024), 0), "-", "-", "-", "-", "-"])
tab(["Corpus", "Docs", "Trechos", "Texto (MB)", "Vetores (MB)", "texts.bin (MB)", "SQLite (MB)",
     "Ingestão (s)", "Trechos/s", "Pico RSS (MB)"], linhas,
    "Tabela 3. Corpus sintético e índice (semente 42). XL é uma matriz aleatória de 1 GiB usada só na Parte E.",
    pesos=[1, 1, 1.3, 1.1, 1.2, 1.3, 1.1, 1.1, 1.1, 1.2])
p("**Corpus.** Documentos em português gerados por `corpus.py`, cada um de um entre dez tópicos de SO e IA (memória virtual, escalonamento, sistemas de arquivos, sincronização, embeddings, RAG, cache, armazenamento, inferência de LLM e GPU), com 8 a 40 frases que misturam termos do tópico e palavras comuns. Não há dados pessoais.")
p("**Fragmentação e embeddings.** Trechos de até 400 caracteres com sobreposição de 50, cortados em limite de palavra. Cada token (sem stopwords) é mapeado por CRC32 para uma das 256 dimensões e um sinal; o vetor é normalizado, de modo que o produto escalar é a similaridade de cosseno. A ingestão processa trechos em lotes (4.096 por padrão; variado no C5b).")
p("**Índice.** `vectors.f32` guarda a matriz N×256 em float32 contígua, sem cabeçalho, o que permite tanto `read()` do arquivo inteiro quanto `mmap()`; `texts.bin` e `offsets.i64` dão acesso direto ao texto de cada trecho; `chunks.db` (SQLite, WAL) guarda documentos e trechos. O carregamento valida o tamanho esperado de `vectors.f32` a partir de `meta.json` e levanta `IndiceIndisponivel` se o arquivo faltar ou estiver truncado.")
p("**Cache de respostas.** Chave = conjunto ordenado dos tokens da consulta sem stopwords, de modo que mudanças de ordem, caixa e pontuação colidem. Capacidade configurável (0 desliga), políticas LRU e FIFO, três modos de concorrência (`none`, `lock`, `singleflight`) e contadores de acertos, erros, remoções, cálculos redundantes e tempo economizado (soma do custo original das entradas reutilizadas).")

h1("6. Processos, threads, filas e recursos compartilhados")
p("Cada execução é um processo com, no pico, uma thread principal, um amostrador, dois produtores e de um a quatro trabalhadores. Os nomes são gravados no kernel com `prctl(PR_SET_NAME)`, o que os torna visíveis em `ps -L` e `/proc/PID/task/*/comm` (evidência em `results/evidence/processo_vivo.txt`, Anexo A). Na amostra com quatro trabalhadores, eles estavam em `hrtimer_nanosleep` (esperando o servidor de inferência simulado) e os produtores em `futex_do_wait` (bloqueados no semáforo `empty` da fila cheia); apareceu também uma thread sem nome com 92% de CPU, o pool do OpenBLAS que o NumPy usa na multiplicação M·q, um lembrete de que bibliotecas nativas criam threads que o código Python não declara. A Tabela 4 lista os recursos compartilhados e a proteção de cada um.")
tab(["Recurso compartilhado", "Quem acessa", "Risco sem proteção", "Mecanismo adotado"],
    [["Buffer de requisições (deque)", "produtores e trabalhadores", "perda ou duplicação de itens, consumidor lendo fila vazia", "semáforos empty/full + mutex; timeout em put/get"],
     ["Cache de respostas (OrderedDict)", "trabalhadores", "atualização perdida nos contadores, cálculo duplicado, exceção ao remover", "mutex; singleflight (Event por chave)"],
     ["Arquivo de log", "todas as threads", "linhas intercaladas e JSON inválido", "mutex + um único write() por linha (O_APPEND)"],
     ["Lista de resultados e contadores", "trabalhadores, produtores", "atualização perdida", "mutex"],
     ["Matriz de vetores e textos", "trabalhadores (só leitura)", "nenhum (imutável após a carga)", "sem trava; mmap compartilhado"],
     ["Conexão SQLite", "trabalhadores", "uso de objeto sqlite3 entre threads", "uma conexão por thread (threading.local), modo somente leitura"],
     ["Memo de tokens do embedder", "trabalhadores", "corrida benigna (mesmo valor gravado)", "sem trava, documentado"]],
    "Tabela 4. Recursos compartilhados e sincronização.", pesos=[2.4, 2, 3, 3], esquerda=(1, 2, 3), fonte=15)

h1("7. Estratégia de sincronização")
p("**Produtores e consumidores (Opção 1).** `BoundedBuffer` usa `empty` (vagas, inicia na capacidade), `full` (itens, inicia em zero) e `mutex` (protege o deque e as estatísticas). `put()` faz `empty.acquire(timeout)`, insere sob o mutex e libera `full`; `get()` faz o inverso. O timeout transforma fila cheia em rejeição controlada, com retentativa e recuo exponencial no produtor, em vez de bloqueio indefinido. O encerramento usa uma pílula `PARAR` por trabalhador, inserida depois que todos os produtores terminam.")
p("**Cache compartilhado (Opção 2).** No modo `none` a leitura e a gravação não têm exclusão mútua, e uma pausa `time.sleep(0)` entre ler e escrever cada contador amplia a janela de corrida para torná-la reproduzível. No modo `lock` o mutex protege a estrutura e os contadores, mas o cálculo da resposta fica fora da região crítica para não serializar a geração; por isso dois trabalhadores que erram a mesma chave ao mesmo tempo ainda calculam duas vezes. O modo `singleflight` resolve isso: o primeiro registra um `threading.Event` para a chave e calcula; os demais esperam o evento e então leem o resultado. O custo é espera, e não CPU.")
p("**Log.** A linha JSON é montada inteira e gravada com um único `os.write()` sob mutex num descritor aberto com O_APPEND. A falha controlada grava a mesma linha em fragmentos de 16 bytes sem mutex.")
p("**Deadlock e starvation.** O risco de espera circular entre a trava do índice e a do cache é demonstrado num processo isolado, com três versões: ingênua (ordens opostas, encerrada pelo processo pai após 3 s), com `acquire(timeout)` e recuo aleatório (detecção e recuperação) e com ordem global de aquisição (prevenção). Starvation é mostrada com uma trava leitores/escritor com preferência a leitores, comparada à versão com preferência a escritores.")

h1("8. Metodologia")
p("Cada configuração foi executada **três vezes**, sempre em processo novo, para que RSS, faltas de página e contadores de E/S não herdem estado. A máquina não tinha outras cargas relevantes durante as medições, e os experimentos rodaram em sequência. Todos os parâmetros, horários e resultados brutos estão nos CSVs de `results/raw/`; as tabelas e figuras deste relatório são geradas por `experiments/analise.py` a partir deles (média de três repetições; barras de erro = desvio-padrão). Os fatores variados foram: número de trabalhadores (1, 2 e 4), tamanho do corpus (S, M, L, XL), capacidade da fila (2, 4, 16, 64), tamanho e política do cache (0, 8, 64; LRU, FIFO), tamanho do contexto (top-k 4 e 64), lote de embeddings (256, 4.096, 65.536), modo de leitura (read, mmap, madvise) e limite de memória (cgroup).")
tab(["Config.", "O que varia", "Fixo", "Métricas principais"],
    [["C1/C2", "read x mmap; S, M, L, XL; varredura x acesso esparso (256 linhas); cache frio (drop_caches) x quente; madvise", "processo novo por medida", "tempo de carga e 1º acesso, RSS anônima e de arquivo, VSZ, faltas de página, bytes lidos"],
     ["C3", "1, 2, 4 trabalhadores; fila 4 e 64; carga de E/S x CPU", "2 produtores, 120 req., corpus M, sem cache", "vazão, latência média e p95, espera na fila, tamanho máx. da fila, utilização"],
     ["C4", "carga repetida, paráfrase, mista e distinta; cache 0/8/64; LRU/FIFO; lock/singleflight", "2 trab., 150 req., chegada 10 ms", "taxa de acerto, remoções, recuperações evitadas, tempo economizado"],
     ["C5", "corpus S/M/L x read/mmap x contexto; lote; cgroup 64 a 384 MB, com e sem swap", "2 trab., cache desligado", "RSS, VSZ, faltas maiores, bytes lidos, swap, latência, OOM"],
     ["C6", "arquivo ausente, índice ausente/truncado, fila saturada, limite de memória, falha de serviço externo", "corpus S, M ou L", "código de saída, erros, retentativas, descartes, recuperação"],
     ["D", "sem e com proteção; servidor e micro-testes; deadlock; starvation", "8 threads nos micro-testes", "atualizações perdidas, cálculos redundantes, linhas corrompidas, bloqueios"]],
    "Tabela 5. Configurações experimentais (três repetições cada).", pesos=[1, 4, 2.6, 3.4], esquerda=(1, 2, 3), fonte=15)
p("**Ferramentas.** `/proc/self/status` (VmRSS, VmSize, VmHWM, RssAnon, RssFile, VmSwap, Threads), `/proc/self/io` (rchar, read_bytes, syscr), `getrusage` (faltas menores e maiores, trocas de contexto), `mincore` via ctypes (fração do arquivo no cache de páginas), `strace -c` e `strace -e`, `ps -L`, `pidstat -t`, `vmstat 1`, `iostat -xz 1` e os contadores do cgroup (`memory.failcnt`, `memory.oom_control`). Cache frio = `sync; echo 3 > /proc/sys/vm/drop_caches` mais `posix_fadvise(DONTNEED)` no arquivo. Os limites de memória foram aplicados por cgroup filho do próprio processo de experimento, de modo que nada fora dele foi afetado.")
p("**Geração simulada.** Espera = tokens de contexto / 20.000 tok/s + 16 tokens de saída / 400 tok/s, cerca de 65 ms por resposta com 500 tokens de contexto. A carga de CPU do C3 substitui a espera por cerca de 40 ms de trabalho fixo em Python puro (calibrado no início do processo).")

exec(open(os.path.join(AQUI, "secoes_resultados.py"), encoding="utf-8").read())
