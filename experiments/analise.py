"""Gera tabelas (Markdown + CSV agregados) e graficos a partir de results/raw.

Media e desvio-padrao sobre as repeticoes de cada configuracao.
Uso: python3 experiments/analise.py
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(RAIZ, "results", "raw")
TAB = os.path.join(RAIZ, "results", "tables")
FIG = os.path.join(RAIZ, "results", "figures")
os.makedirs(TAB, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

# paleta categorica (ordem fixa) e tinta de texto
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
TXT, TXT2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": TXT2,
    "axes.labelcolor": TXT, "xtick.color": TXT2, "ytick.color": TXT2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRADE, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "figure.dpi": 110, "savefig.dpi": 200,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": TXT,
})
NUM = {}


def ler(nome):
    p = os.path.join(RAW, nome)
    return pd.read_csv(p) if os.path.exists(p) else None


def salvar_tab(df, nome, titulo, casas=3):
    df.to_csv(os.path.join(TAB, nome + ".csv"), index=False)
    with open(os.path.join(TAB, nome + ".md"), "w") as f:
        f.write(f"### {titulo}\n\n")
        f.write(df.to_markdown(index=False, floatfmt=f".{casas}f"))
        f.write("\n")


def ms(x):
    return x * 1000.0


def agg(df, chaves, cols):
    g = df.groupby(chaves, sort=False)[cols]
    m = g.mean()
    s = g.std().fillna(0)
    out = m.copy()
    for c in cols:
        out[c + "_sd"] = s[c]
    return out.reset_index()


def barras(ax, grupos, series, valores, erros=None, cores=None, fmt="{:.2f}", rotulos=True):
    n = len(series)
    larg = 0.8 / n
    x = np.arange(len(grupos))
    for i, s in enumerate(series):
        v = valores[i]
        e = erros[i] if erros is not None else None
        b = ax.bar(x + (i - (n - 1) / 2) * larg, v, larg * 0.92, yerr=e, label=s,
                   color=cores[i], error_kw={"elinewidth": 0.8, "ecolor": TXT2, "capsize": 2})
        if rotulos:
            for r, val in zip(b, v):
                ax.annotate(fmt.format(val), (r.get_x() + r.get_width() / 2, r.get_height()),
                            ha="center", va="bottom", fontsize=6.5, color=TXT2,
                            xytext=(0, 1.5), textcoords="offset points")
    ax.set_xticks(x)
    ax.set_xticklabels(grupos)


# ------------------------------------------------------------------ corpus
def corpus():
    linhas = []
    for c in ("S", "M", "L"):
        p = os.path.join(RAW, f"ingest_{c}.json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        linhas.append({"corpus": c, "documentos": d["n_docs"], "trechos": d["n_trechos"],
                       "corpus_MB": d["bytes_corpus"] / 2**20, "vetores_MB": d["bytes_vetores"] / 2**20,
                       "textos_MB": d["bytes_textos"] / 2**20, "sqlite_MB": d["bytes_db"] / 2**20,
                       "ingestao_s": d["t_total_s"], "embedding_s": d["t_embedding_s"],
                       "trechos_por_s": d["trechos_por_s"], "pico_rss_MB": d["pico_rss_mb"],
                       "write_MB": d["write_bytes"] / 2**20})
    xl = os.path.join(RAIZ, "index", "XL_vectors.f32")
    df = pd.DataFrame(linhas)
    salvar_tab(df, "t_corpus", "Corpus e indice", 2)
    NUM["corpus"] = df.to_dict("records")
    if os.path.exists(xl):
        NUM["xl_mb"] = os.path.getsize(xl) / 2**20


# ------------------------------------------------------------------ C1/C2
def c1c2():
    d = ler("c1c2_io.csv")
    if d is None:
        return
    base = d[d.madvise == "nenhum"].copy()
    base["t_total_ms"] = ms(base.t_total_s)
    base["t_carga_ms"] = ms(base.t_carga_s)
    base["t_acesso1_ms"] = ms(base.t_acesso1_s)
    base["t_acesso2_ms"] = ms(base.t_acesso2_s)
    base["read_MB"] = base.read_bytes / 2**20
    cols = ["t_carga_ms", "t_acesso1_ms", "t_acesso2_ms", "t_total_ms", "delta_rss_mb",
            "rss_anon_mb", "rss_file_mb", "delta_vsz_mb", "minflt_carga", "minflt_acesso1",
            "majflt_acesso1", "read_MB", "syscr", "residencia_depois"]
    a = agg(base, ["corpus", "acesso", "modo", "estado_cache"], cols)
    ordem = {"S": 0, "M": 1, "L": 2, "XL": 3}
    a["o"] = a.corpus.map(ordem)
    a = a.sort_values(["acesso", "o", "modo", "estado_cache"]).drop(columns="o")
    tab = a[["corpus", "acesso", "modo", "estado_cache", "t_carga_ms", "t_acesso1_ms",
             "t_total_ms", "t_total_ms_sd", "delta_rss_mb", "rss_anon_mb", "rss_file_mb",
             "minflt_carga", "minflt_acesso1", "majflt_acesso1", "read_MB", "delta_vsz_mb",
             "residencia_depois"]]
    salvar_tab(tab, "t_c1c2", "C1 x C2: leitura convencional (read) x mmap, media de 3 repeticoes", 2)
    NUM["c1c2"] = tab.to_dict("records")

    adv = d[d.madvise != "nenhum"].copy()
    if len(adv):
        adv["t_acesso1_ms"] = ms(adv.t_acesso1_s)
        adv["read_MB"] = adv.read_bytes / 2**20
        ref = base[(base.corpus == "L") & (base.acesso == "varredura") & (base.modo == "mmap") &
                   (base.estado_cache == "frio")].copy()
        ref["madvise"] = "nenhum"
        t = agg(pd.concat([ref, adv]), ["madvise"], ["t_acesso1_ms", "majflt_acesso1",
                                                     "minflt_acesso1", "read_MB"])
        salvar_tab(t, "t_madvise", "mmap com madvise (L, varredura, cache frio)", 2)
        NUM["madvise"] = t.to_dict("records")

    # figura 1: tempo total por tamanho, por padrao de acesso
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=True)
    for ax, acesso in zip(axs, ("varredura", "esparso")):
        s = a[a.acesso == acesso]
        grupos = ["S", "M", "L", "XL"]
        series, vals, errs = [], [], []
        for modo, est in (("read", "frio"), ("mmap", "frio"), ("read", "quente"), ("mmap", "quente")):
            q = s[(s.modo == modo) & (s.estado_cache == est)].set_index("corpus").reindex(grupos)
            series.append(f"{modo} {est}")
            vals.append(q.t_total_ms.values)
            errs.append(q.t_total_ms_sd.values)
        barras(ax, grupos, series, vals, errs, [C1, C2, "#9fc3ef", "#f5b597"], fmt="{:.1f}",
               rotulos=False)
        ax.set_yscale("log")
        ax.set_title(f"Acesso: {acesso}")
        ax.set_xlabel("arquivo de vetores (S 2,6 MB; M 26 MB; L 212 MB; XL 1 GB)", fontsize=7)
    axs[0].set_ylabel("abertura + carga + 1º acesso (ms, log)")
    axs[1].legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "f1_c1c2_tempo.png"))
    plt.close(fig)

    # figura 2: RSS anonima x de arquivo (L e XL)
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.7), sharey=False)
    for ax, corp in zip(axs, ("L", "XL")):
        s = a[(a.corpus == corp) & (a.estado_cache == "quente")]
        rot, anon, arq = [], [], []
        for acesso in ("varredura", "esparso"):
            for modo in ("read", "mmap"):
                q = s[(s.acesso == acesso) & (s.modo == modo)].iloc[0]
                rot.append(f"{modo}\n{acesso}")
                anon.append(q.rss_anon_mb)
                arq.append(q.rss_file_mb)
        x = np.arange(len(rot))
        ax.bar(x, anon, 0.6, color=C1, label="RSS anônima")
        ax.bar(x, arq, 0.6, bottom=np.array(anon) + 0.0, color=C2, label="RSS de arquivo",
               edgecolor="white", linewidth=1)
        for xi, (an, ar) in enumerate(zip(anon, arq)):
            ax.annotate(f"{an + ar:.0f} MB", (xi, an + ar), ha="center", va="bottom",
                        fontsize=7, color=TXT2, xytext=(0, 1.5), textcoords="offset points")
        ax.set_xticks(x)
        ax.set_xticklabels(rot, fontsize=7.5)
        ax.set_title(f"{corp}: memória residente após o acesso")
        ax.set_ylabel("MB")
    axs[0].legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "f2_c1c2_rss.png"))
    plt.close(fig)


# ------------------------------------------------------------------ C3
def c3():
    d = ler("c3_concorrencia.csv")
    if d is None:
        return
    d = d[d.codigo == 0].copy()
    d["p95_ms"] = ms(d["lat_total.p95"])
    d["media_ms"] = ms(d["lat_total.media"])
    d["servico_ms"] = ms(d["lat_servico.media"])
    d["espera_fila_ms"] = ms(d["lat_espera_fila.media"])
    d["espera_put_s"] = d["fila.espera_put_s"]
    cols = ["vazao_rps", "media_ms", "p95_ms", "servico_ms", "espera_fila_ms", "fila.tam_max",
            "fila.tam_medio", "espera_put_s", "fila.puts_bloqueados", "utilizacao_trabalhadores",
            "threads_pico", "memoria.nivcsw", "memoria.nvcsw", "wall_s", "correcao.perdidas",
            "correcao.duplicadas"]
    a = agg(d, ["carga_tipo", "capacidade", "trabalhadores"], cols)
    tab = a[["carga_tipo", "capacidade", "trabalhadores", "vazao_rps", "vazao_rps_sd", "media_ms",
             "p95_ms", "servico_ms", "espera_fila_ms", "fila.tam_max", "fila.tam_medio",
             "utilizacao_trabalhadores", "threads_pico", "memoria.nivcsw", "correcao.perdidas",
             "correcao.duplicadas"]]
    salvar_tab(tab, "t_c3", "C3: concorrencia e fila (2 produtores, 120 requisicoes, media de 3)", 2)
    NUM["c3"] = tab.to_dict("records")

    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.8))
    for carga, cor, nome in (("es", C1, "limitada por E/S (espera do serviço)"),
                             ("cpu", C2, "limitada por CPU (Python puro, GIL)")):
        s = a[(a.carga_tipo == carga) & (a.capacidade == 64)]
        axs[0].errorbar(s.trabalhadores, s.vazao_rps, yerr=s.vazao_rps_sd, marker="o", ms=5,
                        lw=2, color=cor, label=nome, capsize=2)
        axs[1].errorbar(s.trabalhadores, s.servico_ms, yerr=s.servico_ms_sd, marker="o", ms=5,
                        lw=2, color=cor, label=nome, capsize=2)
        for _, r in s.iterrows():
            axs[0].annotate(f"{r.vazao_rps:.1f}", (r.trabalhadores, r.vazao_rps), fontsize=7,
                            color=TXT2, xytext=(4, -9), textcoords="offset points")
    for ax in axs:
        ax.set_xticks([1, 2, 4])
        ax.set_xlabel("trabalhadores (threads consumidoras)")
    axs[0].set_ylabel("vazão (requisições/s)")
    axs[0].set_title("Vazão")
    axs[1].set_ylabel("tempo de serviço médio (ms)")
    axs[1].set_title("Tempo de serviço por requisição")
    axs[0].legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "f3_c3_vazao.png"))
    plt.close(fig)

    # serie temporal de uma execucao (fila e trabalhadores ocupados)
    ts = os.path.join(RAW, "c3", "c3_es_cap64_w2_r1.timeseries.csv")
    if os.path.exists(ts):
        t = pd.read_csv(ts)
        fig, axs = plt.subplots(2, 1, figsize=(7.2, 2.9), sharex=True)
        axs[0].plot(t.t, t.fila, color=C1, lw=2)
        axs[0].set_ylabel("itens na fila")
        axs[0].set_title("Execução C3 (E/S, capacidade 64, 2 trabalhadores): fila e ocupação")
        axs[1].step(t.t, t.ocupados, color=C2, lw=2, where="post")
        axs[1].set_ylabel("trabalhadores\nocupados")
        axs[1].set_xlabel("tempo (s)")
        axs[1].set_yticks([0, 1, 2])
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, "f4_c3_serie.png"))
        plt.close(fig)


# ------------------------------------------------------------------ C4
def c4():
    d = ler("c4_cache.csv")
    if d is None:
        return
    d = d[d.codigo == 0].copy()
    d["cfg"] = d.apply(lambda r: "sem cache" if r.cache_tam == 0 else
                       f"{r.cache_tam} {r.politica.upper()}" + (" SF" if r.modo == "singleflight" else ""), axis=1)
    d["media_ms"] = ms(d["lat_total.media"])
    d["p95_ms"] = ms(d["lat_total.p95"])
    d["servico_ms"] = ms(d["lat_servico.media"])
    d["recuperacoes"] = d["cache.calculos"]
    cols = ["cache.taxa_acerto", "cache.acertos", "cache.erros", "cache.remocoes",
            "cache.calculos_redundantes", "cache.economia_s", "recuperacoes", "servico_ms",
            "media_ms", "p95_ms", "vazao_rps", "wall_s"]
    a = agg(d, ["carga", "cfg"], cols)
    tab = a[["carga", "cfg", "cache.taxa_acerto", "cache.acertos", "cache.erros",
             "cache.remocoes", "cache.calculos_redundantes", "recuperacoes", "cache.economia_s",
             "servico_ms", "p95_ms", "wall_s"]]
    salvar_tab(tab, "t_c4", "C4: cache compartilhado (150 requisicoes, 2 trabalhadores, media de 3)", 3)
    NUM["c4"] = tab.to_dict("records")

    cargas = ["repetida", "parafrase", "mista", "distinta"]
    nomes_cargas = ["repetida", "paráfrase", "mista", "distinta"]
    cfgs = ["8 LRU", "8 FIFO", "64 LRU", "64 LRU SF"]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9))
    vals = [[a[(a.carga == c) & (a.cfg == g)]["cache.taxa_acerto"].mean() * 100 for c in cargas]
            for g in cfgs]
    barras(axs[0], nomes_cargas, cfgs, vals, None, [C1, "#9fc3ef", C2, C3], fmt="{:.0f}")
    axs[0].set_ylabel("taxa de acerto (%)")
    axs[0].set_title("Taxa de acerto por carga")
    axs[0].set_ylim(0, 118)
    axs[0].legend(fontsize=6.5, loc="upper center", ncol=4, handlelength=1.2, columnspacing=0.8)
    cfgs2 = ["sem cache", "8 LRU", "64 LRU", "64 LRU SF"]
    vals2 = [[a[(a.carga == c) & (a.cfg == g)]["servico_ms"].mean() for c in cargas] for g in cfgs2]
    barras(axs[1], nomes_cargas, cfgs2, vals2, None, [TXT2, C1, C2, C3], fmt="{:.0f}")
    axs[1].set_ylabel("tempo de serviço médio (ms)")
    axs[1].set_title("Custo por requisição")
    axs[1].set_ylim(0, 88)
    axs[1].legend(fontsize=6.5, loc="upper center", ncol=4, handlelength=1.2, columnspacing=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "f5_c4_cache.png"))
    plt.close(fig)


# ------------------------------------------------------------------ C5
def c5():
    d = ler("c5a_corpus_contexto.csv")
    if d is not None:
        d = d[d.codigo == 0].copy()
        d["rec_ms"] = ms(d["lat_recuperacao.media"])
        d["ger_ms"] = ms(d["lat_geracao.media"])
        d["p95_ms"] = ms(d["lat_total.p95"])
        d["servico_ms"] = ms(d["lat_servico.media"])
        cols = ["t_carga_indice_s", "memoria.rss_apos_carga_mb", "memoria.rss_pico_mb",
                "memoria.rss_anon_fim_mb", "memoria.rss_file_fim_mb", "memoria.vsz_pico_mb",
                "memoria.minflt", "memoria.majflt", "memoria.mem_available_min_mb", "rec_ms",
                "ger_ms", "servico_ms", "p95_ms", "contexto_trechos_medio", "contexto_tokens_medio",
                "contexto_bytes_medio", "io.rchar"]
        a = agg(d, ["corpus", "modo", "contexto"], cols)
        a["t_carga_indice_ms"] = ms(a.t_carga_indice_s)
        tab = a[["corpus", "modo", "contexto", "t_carga_indice_ms", "memoria.rss_apos_carga_mb",
                 "memoria.rss_pico_mb", "memoria.rss_anon_fim_mb", "memoria.rss_file_fim_mb",
                 "memoria.vsz_pico_mb", "memoria.minflt", "rec_ms", "ger_ms", "servico_ms",
                 "contexto_trechos_medio", "contexto_tokens_medio"]]
        salvar_tab(tab, "t_c5a", "C5a: tamanho do corpus, modo de E/S e contexto (media de 3)", 2)
        NUM["c5a"] = tab.to_dict("records")

        fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.8))
        grupos = ["S", "M", "L"]
        for modo, cor in (("read", C1), ("mmap", C2)):
            s = a[(a.modo == modo) & (a.contexto == "pequeno")].set_index("corpus").reindex(grupos)
            axs[0].plot(grupos, s["memoria.rss_pico_mb"], marker="o", ms=5, lw=2, color=cor,
                        label=f"{modo}: pico RSS")
            axs[0].plot(grupos, s["memoria.rss_apos_carga_mb"], marker="s", ms=4, lw=1.2, ls="--",
                        color=cor, label=f"{modo}: RSS após carga")
            axs[1].plot(grupos, s["rec_ms"], marker="o", ms=5, lw=2, color=cor, label=f"{modo}")
        axs[0].set_ylabel("MB")
        axs[0].set_title("Memória residente x corpus")
        axs[0].legend(fontsize=6.5)
        axs[1].set_ylabel("recuperação média (ms)")
        axs[1].set_title("Tempo de recuperação x corpus")
        axs[1].legend(fontsize=7)
        for ax in axs:
            ax.set_xlabel("corpus (S 2,7 mil; M 27 mil; L 217 mil trechos)")
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, "f6_c5a_corpus.png"))
        plt.close(fig)

    b = ler("c5b_lote_ingestao.csv")
    if b is not None:
        t = agg(b, ["lote_cfg"], ["t_total_s", "t_embedding_s", "pico_rss_mb", "maxrss_mb",
                                  "trechos_por_s", "minflt"])
        salvar_tab(t, "t_c5b", "C5b: lote de embeddings na ingestao do corpus M (media de 3)", 2)
        NUM["c5b"] = t.to_dict("records")

    c = ler("c5c_cgroup.csv")
    if c is not None:
        c = c.copy()
        c["status"] = c.codigo.map(lambda x: "ok" if str(x) == "0" else
                                   ("OOM (SIGKILL)" if str(x) == "-9" else str(x)))
        for col, nova in (("lat_recuperacao.media", "rec_ms"), ("lat_total.p95", "p95_ms"),
                          ("lat_servico.media", "servico_ms")):
            if col in c:
                c[nova] = ms(c[col])
        if "io.read_bytes" in c:
            c["disco_lido_MB"] = c["io.read_bytes"] / 2**20
        cols = [x for x in ["rec_ms", "servico_ms", "p95_ms", "wall_s", "memoria.majflt",
                            "memoria.minflt", "disco_lido_MB", "memoria.rss_pico_mb",
                            "memoria.swap_pico_mb", "cg.memory.failcnt", "duracao_proc_s"] if x in c]
        g = c.groupby(["modo", "limite_mb", "swap"], sort=False)
        a = g[cols].mean().reset_index()
        a["execucoes_ok"] = g.apply(lambda x: int((x.codigo.astype(str) == "0").sum())).values
        a["oom_kills"] = g.apply(lambda x: int((x.codigo.astype(str) == "-9").sum())).values
        salvar_tab(a, "t_c5c", "C5c: limite de memoria por cgroup sobre o corpus L (3 repeticoes)", 2)
        NUM["c5c"] = a.to_dict("records")

        m = a[a.modo == "mmap"].copy()
        if len(m):
            m["rot"] = m.limite_mb.map(lambda v: "sem\nlimite" if v == 0 else f"{int(v)} MB")
            fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.6))
            for ax, col, tit, cor in ((axs[0], "memoria.majflt", "faltas de página maiores", C1),
                                      (axs[1], "disco_lido_MB", "MB lidos do disco", C2),
                                      (axs[2], "rec_ms", "recuperação média (ms)", C3)):
                ax.bar(m.rot, m[col], 0.6, color=cor)
                for xi, v in enumerate(m[col]):
                    ax.annotate(f"{v:,.0f}".replace(",", "."), (xi, v), ha="center", va="bottom",
                                fontsize=6.5, color=TXT2, xytext=(0, 1.5), textcoords="offset points")
                ax.set_title(tit, fontsize=8.5)
                ax.tick_params(axis="x", labelsize=7)
            fig.suptitle("C5c: mmap do corpus L sob limite de memória (cgroup, sem swap)",
                         fontsize=9.5, fontweight="bold", color=TXT)
            fig.tight_layout()
            fig.savefig(os.path.join(FIG, "f7_c5c_cgroup.png"))
            plt.close(fig)


# ------------------------------------------------------------------ C6
def c6():
    d = ler("c6_falhas.csv")
    if d is None:
        return
    linhas = []
    for caso, g in d.groupby("caso", sort=False):
        if caso == "arquivo_ausente":
            linhas.append({"caso": caso, "variante": "5 arquivos inexistentes",
                           "resultado": f"{g.docs_ok.mean():.0f} docs ingeridos; {g.falhas.mean():.0f} falhas registradas no log",
                           "codigo": int(g.codigo.iloc[0]), "reps": len(g)})
        elif caso.startswith("indice_"):
            linhas.append({"caso": "indice_indisponivel", "variante": caso.replace("indice_", ""),
                           "resultado": g.resultado.iloc[0][:110], "codigo": int(g.codigo.iloc[0]),
                           "reps": len(g), "duracao_s": round(g.duracao_s.mean(), 2)})
        elif caso == "fila_saturada":
            for (cap, to, rp), h in g.groupby(["capacidade", "timeout_put", "retentativas_put"]):
                linhas.append({"caso": caso, "variante": f"cap={cap}, timeout={to}s, retentativas={rp}",
                               "resultado": f"descartadas {h['correcao.descartadas_fila_cheia'].mean():.1f}/80; "
                                            f"rejeicoes {h['correcao.rejeicoes_put'].mean():.1f}; "
                                            f"espera media {ms(h['lat_espera_fila.media'].mean()):.0f} ms",
                               "codigo": int(h.codigo.iloc[0]), "reps": len(h)})
        elif caso == "limite_memoria":
            for modo, h in g.groupby("modo", sort=False):
                ok = int((h.codigo.astype(str) == "0").sum())
                oom = int((h.codigo.astype(str) == "-9").sum())
                linhas.append({"caso": caso, "variante": f"{modo}, limite 192 MB sem swap",
                               "resultado": f"{ok} concluidas, {oom} mortas por OOM",
                               "codigo": h.codigo.astype(str).iloc[0], "reps": len(h)})
        elif caso == "servico_externo":
            for (tx, rt), h in g.groupby(["taxa_falha", "retentativas"]):
                linhas.append({"caso": caso, "variante": f"falha={tx:.0%}, retentativas={rt}",
                               "resultado": f"erros {h['correcao.erros'].mean():.1f}/100; "
                                            f"retentativas {h['correcao.retentativas_geracao'].mean():.1f}; "
                                            f"servico medio {ms(h['lat_servico.media'].mean()):.0f} ms",
                               "codigo": int(h.codigo.iloc[0]), "reps": len(h)})
        elif caso == "ollama_indisponivel":
            linhas.append({"caso": caso, "variante": "backend ollama, porta sem servico",
                           "resultado": f"erros {g['correcao.erros'].mean():.0f}/10, processo nao caiu",
                           "codigo": int(g.codigo.iloc[0]), "reps": len(g)})
    t = pd.DataFrame(linhas)
    salvar_tab(t, "t_c6", "C6: falhas controladas", 2)
    NUM["c6"] = t.to_dict("records")


# ------------------------------------------------------------------ D
def sync():
    d = ler("d_sincronizacao.csv")
    if d is not None:
        out = []
        for (teste, modo), g in d.groupby(["teste", "modo"], sort=False):
            r = {"teste": teste, "modo": modo, "reps": len(g)}
            if teste == "D1_contador":
                r["falha_media"] = g.perdidas.mean()
                r["metrica"] = f"atualizacoes perdidas de {int(g.esperado.iloc[0])}"
                r["tempo_ms"] = ms(g.tempo_s.mean())
            elif teste == "D2_cache_micro":
                r["falha_media"] = g.calculos_redundantes.mean()
                r["metrica"] = "calculos redundantes em 50 rodadas x 8 threads"
                r["tempo_ms"] = ms(g.tempo_s.mean())
            elif teste == "D3_log_micro":
                r["falha_media"] = g.invalidas.mean()
                r["metrica"] = f"linhas corrompidas de {int(g.esperadas.iloc[0])}"
                r["tempo_ms"] = ms(g.tempo_s.mean())
            elif teste == "D5_deadlock":
                r["falha_media"] = g.encerrado_pelo_pai.mean()
                r["metrica"] = "fracao encerrada pelo pai por timeout"
                r["tempo_ms"] = ms(g.tempo_s.mean())
                r["obs"] = str(g.retentativas.iloc[0])
                try:
                    vals = [sum(json.loads(x)) / 2 for x in g.retentativas if isinstance(x, str) and x != "null"]
                    r["retent_por_thread"] = sum(vals) / len(vals) if vals else 0
                except ValueError:
                    r["retent_por_thread"] = 0
            elif teste == "D6_starvation":
                r["falha_media"] = g.espera_escritor_max_s.mean()
                r["metrica"] = "espera maxima do escritor (s)"
                r["obs"] = f"escritas {g.escritas.mean():.1f}/5; leituras {g.leituras.mean():.0f}"
                r["escritas"] = g.escritas.mean()
            out.append(r)
        t = pd.DataFrame(out)
        salvar_tab(t, "t_d_micro", "Parte D: demonstracoes isoladas (media de 3 repeticoes)", 3)
        NUM["d_micro"] = t.to_dict("records")
        dl = d[(d.teste == "D5_deadlock") & (d.modo == "ingenuo")]
        if len(dl):
            NUM["deadlock_threads"] = dl.threads_no_timeout.iloc[0]
        lg = d[(d.teste == "D3_log_micro") & (d.modo == "unsafe")]
        if len(lg):
            NUM["log_exemplo"] = str(lg.exemplo_corrompido.iloc[0])

        # figura: falha sem protecao x com protecao (um painel por teste, escalas proprias)
        pares = [("D1_contador", "sem_lock_janela", "lock", "D1 atualizações perdidas", 40000),
                 ("D2_cache_micro", "none", "singleflight", "D2 cálculos redundantes", 400),
                 ("D3_log_micro", "unsafe", "lock", "D3 linhas de log corrompidas", 2400)]
        fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.4))
        for ax, (teste, m0, m1, nome, total) in zip(axs, pares):
            q = t[t.teste == teste].set_index("modo")
            vals = [q.loc[m0, "falha_media"], q.loc[m1, "falha_media"]]
            b = ax.bar(["sem proteção", "com proteção"], vals, 0.6, color=[C2, C1])
            for r, v in zip(b, vals):
                ax.annotate(f"{v:,.0f}".replace(",", "."), (r.get_x() + r.get_width() / 2, v),
                            ha="center", va="bottom", fontsize=7.5, color=TXT, xytext=(0, 1.5),
                            textcoords="offset points")
            ax.set_ylim(0, total * 1.12)
            ax.set_title(f"{nome}\n(de {total:,.0f})".replace(",", "."), fontsize=8.5)
            ax.tick_params(axis="x", labelsize=7.5)
        axs[0].set_ylabel("ocorrências (média de 3)")
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, "f8_d_sync.png"))
        plt.close(fig)

    s = ler("d_servidor.csv")
    if s is not None:
        s = s.copy()
        s["modo"] = s.apply(lambda r: next((str(r[c]) for c in ("cfg_cache_modo", "cfg_log_modo")
                                            if c in r and isinstance(r[c], str)), "-"), axis=1)
        cols = [c for c in ["cache.taxa_acerto", "cache.calculos_redundantes", "cache.excecoes",
                            "cache.acertos", "cache.erros", "correcao.log.invalidas",
                            "correcao.log.linhas", "fila.gets_bloqueados", "fila.espera_get_s",
                            "fila.puts_bloqueados", "fila.espera_put_s", "fila.tam_max",
                            "correcao.perdidas", "correcao.duplicadas", "correcao.processadas",
                            "vazao_rps", "lat_servico.media", "utilizacao_trabalhadores"] if c in s]
        a = s.groupby(["teste", "modo"], sort=False)[cols].mean().reset_index()
        a["contagem_cache"] = a["cache.acertos"] + a["cache.erros"]
        salvar_tab(a, "t_d_servidor", "Parte D no servidor (120 requisicoes, media de 3)", 3)
        NUM["d_servidor"] = a.to_dict("records")


def main():
    for f in (corpus, c1c2, c3, c4, c5, c6, sync):
        try:
            f()
            print(f"ok: {f.__name__}")
        except Exception as e:  # um experimento ausente nao impede os demais
            print(f"falhou {f.__name__}: {e!r}")
    with open(os.path.join(TAB, "numeros.json"), "w") as f:
        json.dump(NUM, f, indent=1, ensure_ascii=False, default=float)


if __name__ == "__main__":
    main()
