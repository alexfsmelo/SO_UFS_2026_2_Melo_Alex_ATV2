# -*- coding: utf-8 -*-
# Resultados e analise. Executado dentro de secoes.py.


def linha(df, **kw):
    q = df
    for k, v in kw.items():
        q = q[q[k] == v]
    if len(q) == 0:
        raise KeyError(kw)
    return q.iloc[0]


io = t("t_c1c2")
mad = t("t_madvise")

h1("9. Resultados")
h2("9.1 C1 e C2: leitura convencional x mmap (Parte E)")


def io_r(c, a, m, e):
    return linha(io, corpus=c, acesso=a, modo=m, estado_cache=e)


rows = []
for c in ("L", "XL"):
    for a in ("varredura", "esparso"):
        for m in ("read", "mmap"):
            fr, qt = io_r(c, a, m, "frio"), io_r(c, a, m, "quente")
            rows.append([c, a, m, f(fr.t_total_ms, 1), f(qt.t_total_ms, 1), f(qt.delta_rss_mb, 0),
                         f(qt.rss_anon_mb, 0), f(qt.rss_file_mb, 0),
                         i(fr.minflt_carga + fr.minflt_acesso1), i(fr.majflt_acesso1), f(fr.read_MB, 0)])
tab(["Arquivo", "Acesso", "Modo", "Frio (ms)", "Quente (ms)", "ΔRSS (MB)", "RssAnon", "RssFile",
     "Faltas menores", "Faltas maiores (frio)", "Lido do disco (MB, frio)"], rows,
    "Tabela 6. C1 x C2 para L (212 MB) e XL (1 GiB): abertura + carga + primeiro acesso; média de 3 repetições. S e M em results/tables/t_c1c2.md.",
    pesos=[1, 1.4, 1, 1, 1.1, 1, 1, 1, 1.2, 1.2, 1.3], fonte=15)
fig("f1_c1c2_tempo.png", "Figura 2. Tempo até o primeiro resultado por tamanho de arquivo (escala log). Cache frio = drop_caches antes de cada processo.")
fig("f2_c1c2_rss.png", "Figura 3. Memória residente após o acesso, separada em anônima (heap do processo) e de arquivo (páginas mapeadas do cache de páginas). Cache quente.")

xr_v_f, xm_v_f = io_r("XL", "varredura", "read", "frio"), io_r("XL", "varredura", "mmap", "frio")
xr_v_q, xm_v_q = io_r("XL", "varredura", "read", "quente"), io_r("XL", "varredura", "mmap", "quente")
xr_e_q, xm_e_q = io_r("XL", "esparso", "read", "quente"), io_r("XL", "esparso", "mmap", "quente")
xr_e_f, xm_e_f = io_r("XL", "esparso", "read", "frio"), io_r("XL", "esparso", "mmap", "frio")
lm_e_f = io_r("L", "esparso", "mmap", "frio")
p(f"**Leitura convencional.** Com `read()` o processo aloca um buffer do tamanho do arquivo e o kernel copia nele cada página. O RSS cresce exatamente o tamanho do arquivo (ΔRSS de {f(xr_v_q.delta_rss_mb, 0)} MB no XL), quase tudo memória anônima, e a carga gera {i(xr_v_f.minflt_carga)} faltas de página menores: uma por página de 4 KiB do buffer novo, preenchida com zeros antes da cópia. Por isso o `read()` com cache quente continua caro ({f(xr_v_q.t_total_ms, 0)} ms contra {f(xr_v_f.t_total_ms, 0)} ms frio no XL): o disco sai do caminho, mas a alocação e a cópia ficam. O strace confirma: depois do `openat`, uma única chamada `read(fd, buf, 222569473)` devolve os 212 MB do L de uma vez; no modo mmap, a mesma abertura é seguida de um único `mmap(NULL, 222569472, PROT_READ, MAP_SHARED, fd, 0)` e de nenhum `read()` (Anexo A).")
p(f"**mmap.** Com `mmap()` a carga é instantânea (microssegundos) e só reserva espaço de endereçamento: a VSZ do processo cresce aproximadamente o tamanho do arquivo (ΔVSZ de {f(xm_v_q.delta_vsz_mb, 0)} MB no XL, medido após o acesso), sem que nenhuma página seja lida nesse momento. As páginas entram na primeira vez que são tocadas, como faltas de página: maiores quando vêm do disco ({i(xm_v_f.majflt_acesso1)} na varredura fria do XL, graças ao _readahead_, que traz blocos de páginas por falta) e menores quando já estão no cache ({i(xm_v_q.minflt_acesso1)} na varredura quente). Na varredura, o RSS final é o mesmo do `read()`, mas é RSS **de arquivo**: páginas limpas que pertencem ao cache de páginas e que o kernel pode descartar sob pressão sem swap. Com cache quente, o mmap levou {f(xm_v_q.t_total_ms, 0)} ms contra {f(xr_v_q.t_total_ms, 0)} ms do read no XL, porque não há cópia.")
p(f"**Acesso esparso é onde o mmap domina.** Tocando 256 linhas aleatórias, o mmap ocupou {f(xm_e_q.delta_rss_mb, 0)} MB de RSS no XL contra {f(xr_e_q.delta_rss_mb, 0)} MB do read, e respondeu em {f(xm_e_f.t_total_ms, 1)} ms com cache frio contra {f(xr_e_f.t_total_ms, 0)} ms. Mesmo assim leu {f(xm_e_f.read_MB, 0)} MB do disco para 256 KB úteis: cada falta maior dispara readahead. No L, com cache frio, o acesso esparso deixou {pct(lm_e_f.residencia_depois)} do arquivo no cache de páginas (medido com mincore).")
rows = []
nome = {"nenhum": "padrão", "willneed": "WILLNEED", "sequential": "SEQUENTIAL", "random": "RANDOM"}
for _, r in mad.iterrows():
    rows.append([nome.get(r.madvise, r.madvise), f(r.t_acesso1_ms, 1), i(r.majflt_acesso1), i(r.minflt_acesso1), f(r.read_MB, 0)])
tab(["madvise", "1º acesso (ms)", "Faltas maiores", "Faltas menores", "Lido do disco (MB)"], rows,
    "Tabela 7. Padrão de leitura informado ao kernel: mmap do L, varredura completa, cache frio (3 repetições).",
    pesos=[2, 1.5, 1.5, 1.5, 1.6], fonte=15)
mr = linha(mad, madvise="random")
mw = linha(mad, madvise="willneed")
mn = linha(mad, madvise="nenhum")
p(f"**Padrão de leitura.** `MADV_RANDOM` desliga o readahead: a mesma varredura passou a gerar {i(mr.majflt_acesso1)} faltas maiores (uma por página) e levou {f(mr.t_acesso1_ms, 0)} ms, contra {f(mn.t_acesso1_ms, 0)} ms no padrão. `MADV_WILLNEED` dispara a leitura antecipada logo no `madvise` e reduziu as faltas maiores para {i(mw.majflt_acesso1)}. O total lido do disco é o mesmo nos quatro casos; o que muda é quantas vezes a thread para e espera o disco.")

# ------------------------------------------------------------------ C3
c3 = t("t_c3")
h2("9.2 C3: concorrência e fila")


def c3r(carga, cap, w):
    return linha(c3, carga_tipo=carga, capacidade=cap, trabalhadores=w)


rows = []
for carga, nm in (("es", "E/S"), ("cpu", "CPU")):
    for cap in (4, 64):
        for w in (1, 2, 4):
            r = c3r(carga, cap, w)
            rows.append([nm, cap, w, f(r.vazao_rps, 1), f(r.media_ms, 0), f(r.p95_ms, 0), f(r.servico_ms, 1),
                         f(r.espera_fila_ms, 0), f(r["fila.tam_medio"], 1), pct(r.utilizacao_trabalhadores),
                         i(r.threads_pico)])
tab(["Carga", "Fila", "Trab.", "Vazão (req/s)", "Lat. média (ms)", "p95 (ms)", "Serviço (ms)", "Espera fila (ms)",
     "Fila média", "Utilização", "Threads"], rows,
    "Tabela 8. C3 com 2 produtores e 120 requisições em rajada, cache desligado, corpus M (média de 3). Perdidas e duplicadas: 0 em todas as execuções.",
    pesos=[1, 0.8, 0.8, 1.1, 1.1, 1, 1.1, 1.1, 1, 1.1, 0.9], fonte=15)
fig("f3_c3_vazao.png", "Figura 4. Vazão e tempo de serviço por número de trabalhadores (fila 64). Barras de erro: desvio-padrão de 3 repetições.")
e1, e2, e4 = c3r("es", 64, 1), c3r("es", 64, 2), c3r("es", 64, 4)
u1, u2, u4 = c3r("cpu", 64, 1), c3r("cpu", 64, 2), c3r("cpu", 64, 4)
e4c, e1c = c3r("es", 4, 4), c3r("es", 4, 1)
p(f"**Carga limitada por E/S.** A vazão cresceu de {f(e1.vazao_rps, 1)} para {f(e2.vazao_rps, 1)} e {f(e4.vazao_rps, 1)} req/s com 1, 2 e 4 trabalhadores ({f(e4.vazao_rps / e1.vazao_rps, 2)}x), com tempo de serviço estável em cerca de {f(e4.servico_ms, 0)} ms. Mesmo com só 2 vCPUs, quatro threads escalam porque passam a maior parte do tempo dormindo na espera do \"servidor de inferência\", e a parte de CPU (NumPy) libera o GIL.")
p(f"**Carga limitada por CPU.** Com trabalho fixo em Python puro, a vazão foi {f(u1.vazao_rps, 1)}, {f(u2.vazao_rps, 1)} e {f(u4.vazao_rps, 1)} req/s, e o tempo de serviço de cada requisição subiu de {f(u1.servico_ms, 0)} para {f(u4.servico_ms, 0)} ms: as threads disputam o GIL, então mais trabalhadores só repartem o mesmo núcleo efetivo e aumentam as trocas de contexto involuntárias ({i(u1['memoria.nivcsw'])} para {i(u4['memoria.nivcsw'])}). Para essa carga o mecanismo certo seria multiprocessamento.")
p(f"**Fila.** Como os produtores enviam em rajada, a fila fica quase sempre cheia (média {f(e1['fila.tam_medio'], 1)} de 64). Aumentar a capacidade de 4 para 64 não mudou a vazão ({f(e1c.vazao_rps, 1)} x {f(e1.vazao_rps, 1)} req/s com 1 trabalhador), mas multiplicou a espera na fila ({f(e1c.espera_fila_ms, 0)} para {f(e1.espera_fila_ms, 0)} ms) e o p95. Fila maior só troca bloqueio do produtor por latência do cliente; com fila 4, o tempo de espera aparece como produtor bloqueado no semáforo `empty`. A contenção começa quando a taxa de chegada supera a capacidade de serviço: a partir daí toda folga vira fila (série temporal na Figura A1, Anexo A).")

# ------------------------------------------------------------------ C4
c4 = t("t_c4")
h2("9.3 C4: cache compartilhado")
cfgs = ["sem cache", "8 LRU", "8 FIFO", "64 LRU", "64 FIFO", "64 LRU SF"]
rows = []
for carga in ("repetida", "parafrase", "mista", "distinta"):
    r = [carga.replace("parafrase", "paráfrase")]
    for g in cfgs:
        q = linha(c4, carga=carga, cfg=g)
        r.append(f"{pct(q['cache.taxa_acerto'])} · {f(q.servico_ms, 0)} ms")
    rows.append(r)
tab(["Carga"] + cfgs, rows,
    "Tabela 9. C4: taxa de acerto e tempo médio de serviço por carga e configuração (150 requisições, 2 trabalhadores, média de 3). SF = singleflight.",
    pesos=[1.3, 1.4, 1.4, 1.4, 1.4, 1.4, 1.5], fonte=15)
fig("f5_c4_cache.png", "Figura 5. Taxa de acerto e custo por requisição. Consultas distintas nunca acertam; paráfrases acertam menos que repetições exatas.")
rep64, rep8, rep8f, rep0 = (linha(c4, carga="repetida", cfg=g) for g in ("64 LRU", "8 LRU", "8 FIFO", "sem cache"))
repsf = linha(c4, carga="repetida", cfg="64 LRU SF")
par64 = linha(c4, carga="parafrase", cfg="64 LRU")
dist8 = linha(c4, carga="distinta", cfg="8 LRU")
p(f"**Ganho.** Com consultas repetidas (24 consultas sorteadas com pesos tipo Zipf), o cache de 64 entradas acertou {pct(rep64['cache.taxa_acerto'])} e reduziu as recuperações de {i(rep0.recuperacoes)} para {f(rep64.recuperacoes, 0)}, o tempo médio de serviço de {f(rep0.servico_ms, 0)} para {f(rep64.servico_ms, 0)} ms e a duração total de {f(rep0.wall_s, 2)} para {f(rep64.wall_s, 2)} s; o tempo economizado somado foi {f(rep64['cache.economia_s'], 1)} s. Com consultas distintas a taxa foi 0% e o cache só gerou remoções ({i(dist8['cache.remocoes'])} no cache de 8), sem custo mensurável no tempo de serviço.")
p(f"**Capacidade e política.** Com 8 entradas, menores que o conjunto de 24 consultas, há substituições, e a política importa: LRU acertou {pct(rep8['cache.taxa_acerto'])} e FIFO {pct(rep8f['cache.taxa_acerto'])}, porque o LRU mantém as consultas populares que FIFO descarta por idade. Com 64 entradas tudo cabe e as duas políticas empatam.")
p(f"**Paráfrases.** A normalização (ordem, caixa, pontuação e stopwords) fez paráfrases acertarem {pct(par64['cache.taxa_acerto'])}, abaixo das repetições exatas, porque prefixos como \"qual o papel de\" ou \"quando usar\" acrescentam palavras de conteúdo e mudam a chave. Um cache semântico (vizinho mais próximo do embedding da consulta com limiar) acertaria mais, com risco de devolver a resposta de uma pergunta diferente.")
p(f"**Concorrência no cache.** No modo `lock`, consultas populares que chegam juntas ainda são calculadas mais de uma vez ({f(rep64['cache.calculos_redundantes'], 1)} cálculos redundantes em média); o singleflight zerou esse número ({f(repsf['cache.calculos_redundantes'], 0)}) e levou a taxa de acerto a {pct(repsf['cache.taxa_acerto'])}.")

exec(open(os.path.join(AQUI, "secoes_resultados2.py"), encoding="utf-8").read())
