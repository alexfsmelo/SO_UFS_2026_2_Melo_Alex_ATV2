"""Validacao do repositorio da AV2: estrutura, repeticoes, tabelas x dados brutos,
numeros do relatorio, invariantes de correcao, evidencias e pendencias.

Uso: python3 experiments/validar.py [pasta_do_repositorio]
Saida: linhas [OK], [AVISO] e [FALHA]; codigo de saida 1 se houver FALHA.
"""
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict

RAIZ = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
cont = {"OK": 0, "AVISO": 0, "FALHA": 0}


def rel(msg, nivel="OK"):
    cont[nivel] += 1
    print(f"[{nivel}] {msg}")


def ler_csv(nome):
    p = os.path.join(RAIZ, "results", nome)
    if not os.path.exists(p):
        return None
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def media(vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def fmt(x, n=1):
    s = f"{x:,.{n}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def perto(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol * max(1.0, abs(a), abs(b))


print(f"Validando {RAIZ}\n")

# 1. estrutura -------------------------------------------------------------------
print("== 1. Estrutura e entregaveis")
obrig = ["README.md", "VIDEO.md", "CONTRIBUICAO.md", "DECLARACAO_IA.md", "requirements.txt",
         "run_all.sh", ".gitignore", "genresearch/server.py", "genresearch/bbuffer.py",
         "genresearch/cache.py", "genresearch/logger.py", "genresearch/store.py",
         "experiments/analise.py", "docs/relatorio_AV2_SO_Alex_Melo.pdf",
         "docs/roteiro-video.md", "docs/comandos-video.txt"]
faltam = [a for a in obrig if not os.path.exists(os.path.join(RAIZ, a))]
if faltam:
    rel(f"arquivos ausentes: {', '.join(faltam)}", "FALHA")
else:
    rel(f"{len(obrig)} arquivos obrigatorios presentes")
if os.path.exists(os.path.join(RAIZ, "docs", "slides_AV2_SO_Alex_Melo.pdf")):
    rel("slides em PDF presentes em docs/")
else:
    rel("docs/slides_AV2_SO_Alex_Melo.pdf ainda nao existe (exportar o deck e salvar)", "AVISO")

# 2. seguranca -------------------------------------------------------------------
print("\n== 2. Seguranca e tamanho")
ign = open(os.path.join(RAIZ, ".gitignore"), encoding="utf-8").read()
for padrao in ("data/", "index/", ".env"):
    if padrao in ign:
        rel(f".gitignore cobre {padrao}")
    else:
        rel(f".gitignore nao cobre {padrao}", "FALHA")
envs = [p for p in glob.glob(os.path.join(RAIZ, "**", ".env*"), recursive=True) if ".venv" not in p]
rel("nenhum arquivo .env no repositorio") if not envs else rel(f"arquivos .env: {envs}", "FALHA")
grandes = []
for raiz, dirs, arqs in os.walk(RAIZ):
    dirs[:] = [d for d in dirs if d not in (".venv", "data", "index", ".git")]
    for a in arqs:
        p = os.path.join(raiz, a)
        if os.path.getsize(p) > 50 * 2**20:
            grandes.append(p)
rel("nenhum arquivo versionavel acima de 50 MB") if not grandes else rel(f"arquivos grandes: {grandes}", "FALHA")

# 3. repeticoes --------------------------------------------------------------------
print("\n== 3. Tres repeticoes por configuracao")
chaves = {
    "raw/c3_concorrencia.csv": ["carga_tipo", "capacidade", "trabalhadores"],
    "raw/c4_cache.csv": ["carga", "cache_tam", "politica", "modo"],
    "raw/c5a_corpus_contexto.csv": ["corpus", "modo", "contexto"],
    "raw/c5b_lote_ingestao.csv": ["lote_cfg"],
    "raw/c5c_cgroup.csv": ["modo", "limite_mb", "swap"],
    "raw/d_sincronizacao.csv": ["teste", "modo"],
    "raw/c1c2_io.csv": ["corpus", "acesso", "modo", "estado_cache", "madvise"],
}
for arq, ks in chaves.items():
    linhas = ler_csv(arq)
    if linhas is None:
        rel(f"{arq} ausente", "FALHA")
        continue
    g = defaultdict(int)
    for l in linhas:
        g[tuple(l.get(k, "") for k in ks)] += 1
    ruins = {k: v for k, v in g.items() if v < 3}
    if ruins:
        rel(f"{arq}: {len(ruins)} configuracoes com menos de 3 repeticoes: {list(ruins)[:3]}", "FALHA")
    else:
        rel(f"{arq}: {len(g)} configuracoes, todas com >= 3 repeticoes ({len(linhas)} linhas)")

# 4. tabelas x brutos ----------------------------------------------------------------
print("\n== 4. Tabelas agregadas conferidas contra os dados brutos")


def conferir(nome_tab, nome_raw, ks_tab, ks_raw, col_tab, valor_raw, filtro=lambda l: True, mapa=None):
    tab = ler_csv(f"tables/{nome_tab}.csv")
    raw = ler_csv(f"raw/{nome_raw}")
    if tab is None or raw is None:
        rel(f"{nome_tab}: tabela ou bruto ausente", "FALHA")
        return
    grupos = defaultdict(list)
    for l in raw:
        if filtro(l):
            k = tuple(mapa(l) if mapa else [l[x] for x in ks_raw])
            grupos[k].append(valor_raw(l))
    erros = 0
    n = 0
    for t in tab:
        k = tuple(t[x] for x in ks_tab)
        # normaliza numeros como texto (ex.: "64" x "64.0")
        k2 = None
        for kk in grupos:
            if all(str(a) == str(b) or (num(a) is not None and num(a) == num(b)) for a, b in zip(kk, k)):
                k2 = kk
                break
        if k2 is None:
            continue
        n += 1
        a, b = media(grupos[k2]), num(t[col_tab])
        if a is None and b is None:  # configuracao sem execucao concluida (ex.: todas mortas por OOM)
            continue
        if not perto(a, b, 1e-4):
            erros += 1
    if n == 0:
        rel(f"{nome_tab}: nenhuma linha conferida", "FALHA")
    elif erros:
        rel(f"{nome_tab}.{col_tab}: {erros} de {n} medias nao batem com o bruto", "FALHA")
    else:
        rel(f"{nome_tab}.{col_tab}: {n} medias recalculadas batem com o bruto")


ok0 = lambda l: l.get("codigo") in ("0", "0.0")  # noqa: E731
conferir("t_c3", "c3_concorrencia.csv", ["carga_tipo", "capacidade", "trabalhadores"],
         ["carga_tipo", "capacidade", "trabalhadores"], "vazao_rps", lambda l: num(l["vazao_rps"]), ok0)


def cfg_c4(l):
    tam = int(float(l["cache_tam"]))
    nome = "sem cache" if tam == 0 else f"{tam} {l['politica'].upper()}" + (" SF" if l["modo"] == "singleflight" else "")
    return [l["carga"], nome]


conferir("t_c4", "c4_cache.csv", ["carga", "cfg"], None, "cache.taxa_acerto",
         lambda l: num(l["cache.taxa_acerto"]), ok0, cfg_c4)
conferir("t_c5c", "c5c_cgroup.csv", ["modo", "limite_mb", "swap"], ["modo", "limite_mb", "swap"],
         "rec_ms", lambda l: num(l.get("lat_recuperacao.media")) * 1000 if num(l.get("lat_recuperacao.media")) is not None else None)
conferir("t_c1c2", "c1c2_io.csv", ["corpus", "acesso", "modo", "estado_cache"],
         ["corpus", "acesso", "modo", "estado_cache"], "t_total_ms",
         lambda l: num(l["t_total_s"]) * 1000, lambda l: l["madvise"] == "nenhum")

# 5. numeros do relatorio --------------------------------------------------------------
print("\n== 5. Numeros do relatorio recalculados a partir dos CSVs brutos")
pdf = os.path.join(RAIZ, "docs", "relatorio_AV2_SO_Alex_Melo.pdf")
texto = None
if shutil.which("pdftotext") and os.path.exists(pdf):
    texto = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
    texto = " ".join(texto.split())
    p = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    pags = [l for l in p.splitlines() if l.startswith("Pages:")]
    rel(f"relatorio: {pags[0].split()[-1] if pags else '?'} paginas no total (corpo ate as Referencias + Anexo A)")
else:
    rel("pdftotext ausente: instale poppler-utils para conferir o PDF (sudo apt install poppler-utils)", "AVISO")


def grupo(nome, **kw):
    return [l for l in (ler_csv(f"raw/{nome}") or []) if all(str(l.get(k)) == str(v) for k, v in kw.items())]


casos = []
g = grupo("c3_concorrencia.csv", carga_tipo="es", capacidade="64", trabalhadores="4")
casos.append(("C3 vazao E/S com 4 trabalhadores", f"{fmt(media([num(l['vazao_rps']) for l in g]), 1)} req/s"))
g = grupo("c4_cache.csv", carga="repetida", cache_tam="64", politica="lru", modo="lock")
casos.append(("C4 taxa de acerto (repetida, 64 LRU)", f"acertou {fmt(100 * media([num(l['cache.taxa_acerto']) for l in g]), 0)}%"))
g = grupo("c5c_cgroup.csv", modo="mmap", limite_mb="64", swap="0")
casos.append(("C5c recuperacao mmap sob 64 MB", f"{fmt(1000 * media([num(l['lat_recuperacao.media']) for l in g]), 1)} ms"))
g = grupo("d_sincronizacao.csv", teste="D1_contador", modo="sem_lock_janela")
casos.append(("D1 atualizacoes perdidas", f"{fmt(media([num(l['perdidas']) for l in g]), 0)} de 40.000"))
g = [l for l in grupo("c1c2_io.csv", corpus="XL", acesso="esparso", modo="mmap", estado_cache="quente") if l["madvise"] == "nenhum"]
casos.append(("C2 RSS do mmap esparso no XL", f"{fmt(media([num(l['delta_rss_mb']) for l in g]), 0)} MB de RSS no XL"))
g = [l for l in grupo("c6_falhas.csv", caso="fila_saturada") if num(l["capacidade"]) == 2 and num(l["retentativas_put"]) == 0]
casos.append(("C6 descartes com fila 2", f"{fmt(media([num(l['correcao.descartadas_fila_cheia']) for l in g]), 0)} de 80 descartadas"))
for nome, esperado in casos:
    if texto is None:
        rel(f"{nome}: valor calculado {esperado} (PDF nao conferido)", "AVISO")
    elif esperado in texto:
        rel(f"{nome}: '{esperado}' calculado do bruto e presente no relatorio")
    else:
        rel(f"{nome}: '{esperado}' calculado do bruto NAO encontrado no relatorio", "FALHA")

# 6. invariantes de correcao ----------------------------------------------------------
print("\n== 6. Invariantes de correcao em todas as execucoes do servidor")
seguras = viol = inseguras_log = log_corrompido = 0
for p in glob.glob(os.path.join(RAIZ, "results", "raw", "**", "*.summary.json"), recursive=True):
    s = json.load(open(p, encoding="utf-8"))
    c = s["config"]
    cor = s["correcao"]
    if c["log_modo"] == "unsafe":
        inseguras_log += 1
        log_corrompido += int(cor["log"]["invalidas"] > 0)
        continue
    if c["cache_modo"] == "none":
        continue
    seguras += 1
    if cor["perdidas"] or cor["duplicadas"] or cor["log"]["invalidas"]:
        viol += 1
        print(f"      violacao em {os.path.relpath(p, RAIZ)}: {cor}")
if seguras and not viol:
    rel(f"{seguras} execucoes com mutex: 0 requisicoes perdidas, 0 duplicadas, 0 linhas de log invalidas")
else:
    rel(f"{viol} de {seguras} execucoes com mutex violam as invariantes", "FALHA")
if inseguras_log:
    nivel = "OK" if log_corrompido == inseguras_log else "AVISO"
    rel(f"falha controlada do log: {log_corrompido} de {inseguras_log} execucoes sem mutex produziram linhas invalidas", nivel)

# 7. evidencias ---------------------------------------------------------------------
print("\n== 7. Evidencias do sistema operacional")
ev = os.path.join(RAIZ, "results", "evidence")
for a in ("ambiente.txt", "processo_vivo.txt", "strace_resumo_servidor.txt", "vmstat_c5c.txt",
          "iostat_leitura_fria_XL.txt"):
    if os.path.exists(os.path.join(ev, a)) and os.path.getsize(os.path.join(ev, a)) > 0:
        rel(f"evidence/{a} presente")
    else:
        rel(f"evidence/{a} ausente ou vazio", "FALHA")
for a, trecho in (("strace_read_L_resumo.txt", "read("), ("strace_mmap_L_resumo.txt", "mmap(NULL, 222569472")):
    p = os.path.join(ev, a)
    t = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    rel(f"evidence/{a} contem '{trecho}'") if trecho in t else rel(f"evidence/{a} sem '{trecho}'", "FALHA")
pv = open(os.path.join(ev, "processo_vivo.txt"), encoding="utf-8").read() if os.path.exists(os.path.join(ev, "processo_vivo.txt")) else ""
for trecho in ("worker-0", "produtor-0", "vectors.f32", "RssFile"):
    rel(f"processo_vivo.txt mostra {trecho}") if trecho in pv else rel(f"processo_vivo.txt sem {trecho}", "FALHA")

# 8. pendencias e estilo ------------------------------------------------------------
print("\n== 8. Pendencias e travessoes")
pend = []
trav = []
for raiz, dirs, arqs in os.walk(RAIZ):
    dirs[:] = [d for d in dirs if d not in (".venv", "data", "index", ".git", "raw", "build")]
    for a in arqs:
        if a.endswith((".md", ".txt", ".py", ".sh", ".js")):
            p = os.path.join(raiz, a)
            t = open(p, encoding="utf-8", errors="replace").read()
            if "PREENCHER" in t and not a == "validar.py":
                pend.append(os.path.relpath(p, RAIZ))
            if ("—" in t or "–" in t) and a != "validar.py":
                trav.append(os.path.relpath(p, RAIZ))
if texto is not None and "PREENCHER" in texto:
    pend.append("docs/relatorio_AV2_SO_Alex_Melo.pdf")
rel(f"campos PREENCHER pendentes em: {', '.join(sorted(set(pend)))}", "AVISO") if pend else rel("nenhum campo PREENCHER pendente")
rel(f"travessoes encontrados em: {trav}", "FALHA") if trav else rel("nenhum travessao nos textos")

print(f"\nResumo: {cont['OK']} OK, {cont['AVISO']} avisos, {cont['FALHA']} falhas")
sys.exit(1 if cont["FALHA"] else 0)
