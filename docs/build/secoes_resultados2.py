# -*- coding: utf-8 -*-
# C5, C6, D e analises. Executado dentro de secoes_resultados.py.

c5a = t("t_c5a")
c5b = t("t_c5b")
h2("9.4 C5: pressão de memória")


def c5r(c, m, x):
    return linha(c5a, corpus=c, modo=m, contexto=x)


rows = []
for c in ("S", "M", "L"):
    for m in ("read", "mmap"):
        for x in ("pequeno", "grande"):
            r = c5r(c, m, x)
            rows.append([c, m, x, f(r.t_carga_indice_ms, 1), f(r["memoria.rss_apos_carga_mb"], 0),
                         f(r["memoria.rss_pico_mb"], 0), f(r["memoria.rss_anon_fim_mb"], 0),
                         f(r["memoria.rss_file_fim_mb"], 0), i(r["memoria.minflt"]), f(r.rec_ms, 1),
                         f(r.ger_ms, 0), f(r.contexto_trechos_medio, 1), i(r.contexto_tokens_medio)])
tab(["Corpus", "Modo", "Contexto", "Carga (ms)", "RSS após carga", "Pico RSS", "RssAnon", "RssFile",
     "Faltas menores", "Recup. (ms)", "Geração (ms)", "Trechos", "Tokens"], rows,
    "Tabela 10. C5a: corpus, modo de leitura e contexto (top-k 4 e até 256 tokens; top-k 64 e até 4.096 tokens). 60 requisições, 2 trabalhadores, média de 3. Memória em MB.",
    pesos=[0.9, 0.9, 1.1, 0.9, 1, 0.9, 0.9, 0.9, 1.1, 0.9, 1, 0.9, 0.9], fonte=14)
fig("f6_c5a_corpus.png", "Figura 6. Memória residente e tempo de recuperação em função do corpus (contexto pequeno).", 15)
Lr, Lm = c5r("L", "read", "pequeno"), c5r("L", "mmap", "pequeno")
Sr = c5r("S", "read", "pequeno")
Lmg = c5r("L", "mmap", "grande")
p(f"**Tamanho do corpus.** Com `read`, o RSS logo após carregar o índice acompanha o tamanho dos arquivos: {f(Sr['memoria.rss_apos_carga_mb'], 0)} MB no S e {f(Lr['memoria.rss_apos_carga_mb'], 0)} MB no L (vetores, textos e deslocamentos copiados para memória anônima), com {f(Lr.t_carga_indice_ms, 0)} ms de carga e {i(Lr['memoria.minflt'])} faltas menores. Com `mmap`, a carga leva {f(Lm.t_carga_indice_ms, 2)} ms e o RSS inicial é o do interpretador ({f(Lm['memoria.rss_apos_carga_mb'], 0)} MB); o pico chega a {f(Lm['memoria.rss_pico_mb'], 0)} MB porque a varredura toca a matriz inteira, mas {f(Lm['memoria.rss_file_fim_mb'], 0)} MB disso é RSS de arquivo. A recuperação cresce linearmente com o número de trechos ({f(c5r('S', 'mmap', 'pequeno').rec_ms, 1)} ms no S, {f(Lm.rec_ms, 1)} ms no L): a busca é uma varredura exata, e o custo é de largura de banda de memória, não de disco, já que o arquivo está em cache.")
p(f"**Contexto.** Passar de top-k 4 para 64 trechos (≈{i(Lmg.contexto_tokens_medio)} tokens) aumentou a geração simulada de cerca de {f(Lm.ger_ms, 0)} para {f(Lmg.ger_ms, 0)} ms, porque o custo de _prefill_ cresce com os tokens de entrada, e multiplicou por {f(Lmg['memoria.minflt'] / Lm['memoria.minflt'], 1)} as faltas de página da execução no L com mmap ({i(Lm['memoria.minflt'])} para {i(Lmg['memoria.minflt'])}), porque mais páginas de `texts.bin` são tocadas para montar o contexto. Num LLM real, o mesmo crescimento aparece no KV-cache, que ocupa memória proporcional ao contexto.")
b0, b1, b2 = (linha(c5b, lote_cfg=x) for x in (256, 4096, 65536))
p(f"**Lote.** Na ingestão do corpus M, o pico de RSS foi {f(b0.pico_rss_mb, 0)} MB com lote de 256 trechos, {f(b1.pico_rss_mb, 0)} MB com 4.096 e {f(b2.pico_rss_mb, 0)} MB com 65.536, para tempos praticamente iguais ({f(b0.t_total_s, 2)}, {f(b1.t_total_s, 2)} e {f(b2.t_total_s, 2)} s). Lotes maiores compram pouca vazão com muita memória: o mesmo compromisso do tamanho de lote em inferência e em geração de embeddings com GPU.")

exec(open(os.path.join(AQUI, "secoes_resultados3.py"), encoding="utf-8").read())
