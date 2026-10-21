# -*- coding: utf-8 -*-
# C5c, C6, D e questoes de analise.

c5c = t("t_c5c")
VM = {"si": 0, "so": 0}
for _l in open(os.path.join(RAIZ, "results", "evidence", "vmstat_c5c.txt")):
    _c = _l.split()
    if _c and _c[0].isdigit():
        VM["si"] = max(VM["si"], int(_c[6]))
        VM["so"] = max(VM["so"], int(_c[7]))


def c5cr(m, lim, sw):
    return linha(c5c, modo=m, limite_mb=lim, swap=sw)


rows = []
for _, r in c5c.iterrows():
    lim = "sem limite" if r.limite_mb == 0 else f"{int(r.limite_mb)} MB"
    okn = int(r.execucoes_ok)
    rows.append([r.modo, lim, "sim" if r.swap else "não", f"{okn}/3", int(r.oom_kills),
                 f(r.rec_ms, 1) if okn else "-", f(r.wall_s, 2) if okn else "-",
                 i(r["memoria.majflt"]) if okn else "-", f(r.disco_lido_MB, 0) if okn else "-",
                 f(r["memoria.swap_pico_mb"], 0) if okn else "-", i(r["cg.memory.failcnt"]) if r.limite_mb else "-"])
tab(["Modo", "Limite (cgroup)", "Swap", "Concluídas", "OOM", "Recup. (ms)", "Duração (s)", "Faltas maiores",
     "Lido do disco (MB)", "Swap pico (MB)", "failcnt"], rows,
    "Tabela 11. C5c: corpus L (vetores 212 MB + textos 76 MB) sob limite de memória, 40 requisições, cache frio antes de cada execução. Médias só das execuções concluídas.",
    pesos=[0.9, 1.3, 0.8, 1.1, 0.7, 1, 1, 1.1, 1.2, 1.1, 1], fonte=14)
fig("f7_c5c_cgroup.png", "Figura 7. mmap do corpus L com limites de memória decrescentes: abaixo do tamanho do arquivo, as páginas de arquivo são descartadas e relidas a cada varredura.", 15.5)
ms0, ms64 = c5cr("mmap", 0, 0), c5cr("mmap", 64, 0)
r0, r192 = c5cr("read", 0, 0), c5cr("read", 192, 0)
r256s = c5cr("read", 256, 1)
r192s = c5cr("read", 192, 1)
p(f"**mmap sob limite: degradação.** Sem limite, o mmap do L leu {f(ms0.disco_lido_MB, 0)} MB do disco (uma vez, na primeira varredura) e cada recuperação levou {f(ms0.rec_ms, 1)} ms. Com 64 MB, menos que um terço da matriz, o kernel precisa descartar páginas de arquivo já usadas para trazer as próximas, e a varredura seguinte encontra o arquivo fora da memória: foram {i(ms64['memoria.majflt'])} faltas maiores, {f(ms64.disco_lido_MB, 0)} MB lidos do disco e recuperação de {f(ms64.rec_ms, 1)} ms ({f(ms64.rec_ms / ms0.rec_ms, 1)}x). É o padrão de _thrashing_ de páginas de arquivo: o processo continua correto, mas passa o tempo esperando o disco. Como as páginas são limpas, nada precisou ir para o swap.")
p(f"**read sob limite: falha.** O `read()` precisa de cerca de 336 MB de memória anônima. Com 384 MB coube; com 192 MB e sem swap, as três execuções foram mortas pelo OOM killer do cgroup (SIGKILL, código -9) ainda na carga do índice. Com swap, a memória anônima excedente pode ir para o disco: com 256 MB, {int(r256s.execucoes_ok)} de 3 concluíram, com pico de {f(r256s['memoria.swap_pico_mb'], 0)} MB em swap e recuperação de {f(r256s.rec_ms, 1)} ms contra {f(r0.rec_ms, 1)} ms sem limite. Com 192 MB e swap, {int(r192s.execucoes_ok)} de 3 concluíram e {int(r192s.oom_kills)} {'foi morta' if int(r192s.oom_kills) == 1 else 'foram mortas'}, e as que concluíram ficaram {f(r192s.rec_ms / r0.rec_ms, 0)}x mais lentas: a cada varredura a matriz inteira volta do swap, e quando a recuperação de páginas não acompanha a demanda o OOM killer age mesmo com swap livre. O `vmstat` registrou picos de {i(VM['si'] / 1024)} MB/s em `si` e {i(VM['so'] / 1024)} MB/s em `so` nesses intervalos (results/evidence/vmstat_c5c.txt), a assinatura de swap intenso.")

# ------------------------------------------------------------------ C6
c6 = t("t_c6")
h2("9.5 C6: falhas controladas")
c6r = pd.read_csv(os.path.join(RAIZ, "results", "raw", "c6_falhas.csv"))


def g6(**kw):
    q = c6r
    for k, v in kw.items():
        q = q[q[k] == v]
    return q


aus = g6(caso="arquivo_ausente")
rec = g6(caso="indice_reconstrucao")
fs0 = g6(caso="fila_saturada", capacidade=2.0, retentativas_put=0.0)
fs3 = g6(caso="fila_saturada", capacidade=2.0, retentativas_put=3.0)
fs64 = g6(caso="fila_saturada", capacidade=64.0)
mr_ = g6(caso="limite_memoria", modo="read")
mm_ = g6(caso="limite_memoria", modo="mmap")
e20 = (g6(caso="servico_externo", taxa_falha=0.2, retentativas=0.0), g6(caso="servico_externo", taxa_falha=0.2, retentativas=2.0))
e50 = (g6(caso="servico_externo", taxa_falha=0.5, retentativas=0.0), g6(caso="servico_externo", taxa_falha=0.5, retentativas=2.0))
oll = g6(caso="ollama_indisponivel")
rows = [
    ["Arquivo ausente (ingestão do S)", "5 caminhos inexistentes", f"ingestão concluída com {i(aus.docs_ok.mean())} documentos; {i(aus.falhas.mean())} eventos falha_ingestao no log", "0"],
    ["Índice indisponível", "vectors.f32 apagado", "IndiceIndisponivel: arquivo do índice ausente; nenhuma requisição atendida", "2"],
    ["Índice indisponível", "vectors.f32 truncado pela metade", "inconsistente: 1.380.352 bytes, esperado 2.760.704; servidor não sobe", "2"],
    ["Índice indisponível", "apagado + `--reconstruir-se-ausente`", f"reingestão automática e atendimento normal em {f(rec.duracao_s.mean(), 2)} s", "0"],
    ["Fila saturada (1 trab., 4 prod., 80 req.)", "fila 2, timeout 5 ms, sem retentativa", f"{f(fs0['correcao.descartadas_fila_cheia'].mean(), 0)} de 80 descartadas", "0"],
    ["Fila saturada", "fila 2, timeout 5 ms, 3 retentativas", f"{f(fs3['correcao.descartadas_fila_cheia'].mean(), 0)} descartadas; {f(fs3['correcao.rejeicoes_put'].mean(), 0)} rejeições de put", "0"],
    ["Fila saturada", "fila 64, timeout 30 s", f"0 descartadas; espera média na fila de {f(fs64['lat_espera_fila.media'].mean(), 1)} s", "0"],
    ["Limite de memória (L, cgroup 192 MB, sem swap)", "índice por read()", f"{int((mr_.codigo == -9).sum())} de 3 mortas por OOM (SIGKILL)", "-9"],
    ["Limite de memória", "índice por mmap()", f"{int((mm_.codigo == 0).sum())} de 3 concluídas", "0"],
    ["Serviço externo (100 req.)", "falha 20%: 0 e 2 retentativas", f"erros de {f(e20[0]['correcao.erros'].mean(), 0)} para {f(e20[1]['correcao.erros'].mean(), 0)}; serviço de {f(e20[0]['lat_servico.media'].mean() * 1000, 0)} para {f(e20[1]['lat_servico.media'].mean() * 1000, 0)} ms", "0"],
    ["Serviço externo", "falha 50%: 0 e 2 retentativas", f"erros de {f(e50[0]['correcao.erros'].mean(), 0)} para {f(e50[1]['correcao.erros'].mean(), 0)}; serviço de {f(e50[0]['lat_servico.media'].mean() * 1000, 0)} para {f(e50[1]['lat_servico.media'].mean() * 1000, 0)} ms", "0"],
    ["Ollama indisponível", "porta sem serviço, 1 retentativa", f"{f(oll['correcao.erros'].mean(), 0)} de 10 requisições com erro controlado; trabalhadores seguem", "0"],
]
tab(["Falha", "Variante", "Comportamento observado (média de 3 repetições)", "Saída"], rows,
    "Tabela 12. C6: falhas injetadas e recuperação. Saída 2 = erro controlado com mensagem; -9 = morto pelo OOM killer.",
    pesos=[2.6, 2.8, 5, 0.7], esquerda=(1, 2), fonte=14)
p(f"Todas as falhas foram detectadas e registradas no log com evento próprio (`falha_ingestao`, `fila_cheia`, `requisicao_descartada`, `falha_geracao`). Arquivo ausente não interrompe a ingestão; índice ausente ou truncado é detectado antes de servir (verificação do tamanho esperado de `vectors.f32`) e, com `--reconstruir-se-ausente`, o servidor reconstrói o índice e atende normalmente. Fila saturada com timeout curto descarta requisições (backpressure explícito); retentativas com recuo exponencial reduzem os descartes ao custo de latência; fila grande elimina descartes e transforma o excesso em espera. Falhas do serviço externo viram erros por requisição sem derrubar trabalhadores; duas retentativas com recuo reduziram os erros de {f(e20[0]['correcao.erros'].mean(), 0)} para {f(e20[1]['correcao.erros'].mean(), 0)} (falha de 20%) e de {f(e50[0]['correcao.erros'].mean(), 0)} para {f(e50[1]['correcao.erros'].mean(), 0)} (50%), ao custo de tempo de serviço maior. O limite de memória é a única falha que mata o processo, e a recuperação é de projeto: carregar o índice por mmap.")

# ------------------------------------------------------------------ D
dmi = t("t_d_micro")
dsv = t("t_d_servidor")
h2("9.6 Parte D: sincronização e falhas controladas")


def dm(teste, modo):
    return linha(dmi, teste=teste, modo=modo)


def ds(teste, modo):
    return linha(dsv, teste=teste, modo=modo)


fig("f8_d_sync.png", "Figura 8. Falhas controladas sem proteção e com a sincronização adotada (média de 3 repetições).", 15)
d1n, d1j, d1l = dm("D1_contador", "sem_lock"), dm("D1_contador", "sem_lock_janela"), dm("D1_contador", "lock")
d2n, d2l, d2s = dm("D2_cache_micro", "none"), dm("D2_cache_micro", "lock"), dm("D2_cache_micro", "singleflight")
d3u, d3l = dm("D3_log_micro", "unsafe"), dm("D3_log_micro", "lock")
d5i, d5t, d5o = dm("D5_deadlock", "ingenuo"), dm("D5_deadlock", "timeout"), dm("D5_deadlock", "ordenado")
d6l, d6e = dm("D6_starvation", "pref_leitores"), dm("D6_starvation", "pref_escritor")
sc_n, sc_l, sc_s = ds("D2_cache_servidor", "none"), ds("D2_cache_servidor", "lock"), ds("D2_cache_servidor", "singleflight")
lg_u, lg_l = ds("D3_log_servidor", "unsafe"), ds("D3_log_servidor", "lock")
cb = dsv[dsv.teste == "D4_consumidor_bloqueado"].iloc[0]
pb = dsv[dsv.teste == "D4_produtor_bloqueado"].iloc[0]
rows = [
    ["D1 Contador compartilhado (8 threads × 5.000)", f"{i(d1n.falha_media)} perdidas sem pausa; {i(d1j.falha_media)} com janela", f"0 perdidas; {f(d1l.tempo_ms, 0)} ms contra {f(d1j.tempo_ms, 0)} ms"],
    ["D2 Cache, mesma chave (8 threads × 50 rodadas)", f"{i(d2n.falha_media)} cálculos redundantes (none)", f"lock: {i(d2l.falha_media)}; singleflight: {i(d2s.falha_media)}"],
    ["D2 Cache no servidor (carga repetida, 4 trab.)", f"none: {f(sc_n['cache.calculos_redundantes'], 1)} redundantes; contagem {f(sc_n.contagem_cache, 0)} de 120", f"lock: {f(sc_l['cache.calculos_redundantes'], 1)}; singleflight: {f(sc_s['cache.calculos_redundantes'], 1)}; contagem 120"],
    ["D3 Log (8 threads × 300 linhas)", f"{i(d3u.falha_media)} de 2.400 linhas corrompidas", "0 corrompidas"],
    ["D3 Log no servidor", f"{f(lg_u['correcao.log.invalidas'], 0)} de {f(lg_u['correcao.log.linhas'], 0)} linhas inválidas", f"{f(lg_l['correcao.log.invalidas'], 0)} inválidas"],
    ["D4 Consumidor bloqueado (chegada lenta)", f"{f(cb['fila.gets_bloqueados'], 0)} get() bloqueados; {f(cb['fila.espera_get_s'], 1)} s de espera somada", "comportamento esperado do semáforo full"],
    ["D4 Produtor bloqueado (fila 2, 1 trab.)", f"{f(pb['fila.puts_bloqueados'], 0)} put() bloqueados; {f(pb['fila.espera_put_s'], 1)} s de espera somada", "comportamento esperado do semáforo empty"],
    ["D5 Espera circular (2 travas, ordens opostas)", f"ingênuo: travou nas 3 execuções, encerrado pelo pai após 3 s", f"timeout: concluiu em {f(d5t.tempo_ms / 1000, 2)} s com retentativas; ordenado: {f(d5o.tempo_ms / 1000, 2)} s, 0 retentativas"],
    ["D6 Starvation (6 leitores, 1 escritor)", f"preferência a leitores: escritor esperou {f(d6l.falha_media, 2)} s", f"preferência a escritor: {f(d6e.falha_media * 1000, 1)} ms"],
]
tab(["Demonstração", "Sem proteção (falha)", "Com sincronização"], rows,
    "Tabela 13. Parte D: falhas controladas e correção (média de 3 repetições).", pesos=[3.2, 3.6, 3.6], esquerda=(1, 2), fonte=14)
p(f"**Atualização perdida.** O contador sem mutex não perdeu nada sem a pausa artificial: o GIL só troca de thread a cada 5 ms, e o laço termina antes. A corrida existe, mas é rara, o tipo de defeito que passa nos testes e aparece em produção. Com `sleep(0)` entre ler e gravar, 8 threads perderam {i(d1j.falha_media)} de 40.000 incrementos. Com mutex, nada se perde, mas a mesma janela dentro da região crítica tornou o laço {f(d1l.tempo_ms / d1j.tempo_ms, 1)}x mais lento: quem cede a CPU segurando a trava faz as demais threads acordarem e dormirem de novo (efeito comboio). Regiões críticas devem ser curtas e não bloquear.")
p(f"**Cache e log no servidor.** Sem mutex, os contadores do cache somaram {f(sc_n.contagem_cache, 0)} acertos+erros para 120 requisições, ou seja, atualizações perdidas num componente real, e houve {f(sc_n['cache.calculos_redundantes'], 1)} cálculos redundantes. O mutex corrigiu os contadores, mas não a duplicação ({f(sc_l['cache.calculos_redundantes'], 1)}), porque o cálculo fica fora da região crítica; só o singleflight a eliminou. No log sem mutex e gravado em fragmentos, {f(lg_u['correcao.log.invalidas'], 0)} de {f(lg_u['correcao.log.linhas'], 0)} linhas ficaram inválidas (exemplo no Anexo A).")
p(f"**Deadlock.** A versão ingênua travou nas três execuções; no momento do timeout, as duas threads estavam no estado S com canal de espera `futex_do_wait` (Anexo A), isto é, bloqueadas no kernel esperando uma trava que a outra segura: as quatro condições de Coffman presentes. O processo pai detectou a falta de progresso por timeout e encerrou o filho (SIGTERM, código -15), o mecanismo de encerramento exigido. A versão com `acquire(timeout)` quebra a condição de não preempção: detecta, libera o que tem e tenta de novo após espera aleatória, concluindo com cerca de {i(d5t.retent_por_thread)} retentativas por thread. A versão ordenada quebra a espera circular e é a mais rápida ({f(d5t.tempo_ms / d5o.tempo_ms, 1)}x mais rápida que a com timeout).")
p(f"**Starvation.** Com preferência a leitores e leitores sobrepostos, o escritor esperou {f(d6l.falha_media, 2)} s (praticamente toda a execução) e completou só {f(d6l.escritas, 0)} de 5 escritas; com preferência a escritores, novos leitores esperam quando há escritor na fila, e a espera máxima caiu para {f(d6e.falha_media * 1000, 1)} ms. No servidor, a situação análoga seria uma reindexação (escrita) que nunca consegue a trava porque consultas (leituras) não param de chegar.")

h1("10. Análise de memória, armazenamento, paginação e E/S")
bl(f"**Corpus, índice, lote e contexto x RAM, paginação e latência.** Com `read`, a RAM cresce linearmente com o índice ({f(Sr['memoria.rss_apos_carga_mb'], 0)} para {f(Lr['memoria.rss_apos_carga_mb'], 0)} MB de S para L) e a carga também ({f(Sr.t_carga_indice_ms, 1)} para {f(Lr.t_carga_indice_ms, 0)} ms). A latência de recuperação cresce com o número de trechos porque a busca é exata. Contexto maior toca mais páginas de texto e encarece a geração; lote maior eleva o pico de RSS da ingestão.",
   f"**read x mmap.** read: custo proporcional ao arquivo inteiro, em tempo (cópia e faltas menores de zero-fill) e em memória anônima. mmap: custo proporcional ao que é tocado, com memória de arquivo compartilhável e descartável. No acesso esparso ao XL, {f(xm_e_q.delta_rss_mb, 0)} MB contra {f(xr_e_q.delta_rss_mb, 0)} MB; na varredura com cache quente, {f(xm_v_q.t_total_ms, 0)} contra {f(xr_v_q.t_total_ms, 0)} ms. Na primeira execução (cache frio) os dois são limitados pelo disco; na segunda, o mmap aproveita o cache de páginas sem cópia.",
   f"**Evidência de paginação intensa e swap.** Sim, de forma controlada: mmap sob 64 MB gerou {i(ms64['memoria.majflt'])} faltas maiores e releu {f(ms64.disco_lido_MB, 0)} MB; read sob 256 MB com swap usou até {f(r256s['memoria.swap_pico_mb'], 0)} MB de swap e ficou {f(r256s.rec_ms / r0.rec_ms, 0)}x mais lento; read sob 192 MB sem swap foi morto pelo OOM. Sem limite de cgroup, MemAvailable nunca ficou abaixo de 7 GB, e as faltas maiores foram nulas no C4 e no C5a, com o índice já no cache de páginas.")

h1("11. Análise de concorrência, cache e correção")
bl(f"**O cache reduziu tempo ou operações?** Sim quando há repetição: {pct(rep64['cache.taxa_acerto'])} de acerto, {f(rep64.recuperacoes, 0)} recuperações em vez de 150 e tempo de serviço {f(rep0.servico_ms / rep64.servico_ms, 1)}x menor. Com consultas distintas, 0% e nenhum ganho.",
   f"**A concorrência aumentou a vazão?** Para a carga de E/S, sim: {f(e4.vazao_rps / e1.vazao_rps, 1)}x com 4 trabalhadores em 2 vCPUs. Para CPU em Python puro, o ganho foi limitado pelo GIL. A contenção aparece na fila: quando a chegada supera o serviço, a espera cresce com a capacidade da fila e o p95 explode, sem ganho de vazão.",
   "**Recursos que exigiram exclusão mútua ou sincronização de eventos.** Exclusão mútua: deque da fila, estrutura e contadores do cache, log, lista de resultados. Sincronização de eventos: semáforos `empty`/`full` (há vaga / há item), `Event` do singleflight (resultado pronto), pílula de parada para encerramento.",
   "**Falhas demonstradas.** Atualização perdida, cálculo duplicado, log intercalado, exceções e contadores incoerentes no cache, fila saturada com descarte, consumidor e produtor bloqueados, espera circular (deadlock) isolada e starvation de escritor.",
   f"**Mecanismos e trade-offs.** Mutex: correção com custo baixo em regiões curtas, alto se a região bloqueia (comboio no D1). Semáforos com timeout: backpressure explícito, mas exigem política de retentativa e descarte. Singleflight: elimina trabalho repetido, ao custo de fazer threads esperarem pelo cálculo de outra (e de propagar a falha dela). Ordem global de travas: previne deadlock sem custo em tempo de execução, mas exige disciplina no código; timeout: detecta e recupera, mas desperdiça trabalho ({f(d5t.tempo_ms / d5o.tempo_ms, 1)}x mais lento que o ordenado).")

exec(open(os.path.join(AQUI, "secoes_final.py"), encoding="utf-8").read())
