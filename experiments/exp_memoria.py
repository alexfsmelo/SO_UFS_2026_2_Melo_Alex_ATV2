"""C5: pressao de memoria.

(a) corpus S/M/L x modo read/mmap x contexto pequeno/grande
(b) tamanho do lote de embeddings na ingestao (M)
(c) limite de memoria por cgroup (L): mmap com limites decrescentes (sem swap)
    e read com e sem swap. Limites explicitos; nada afeta o resto do sistema.
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import (PY, RAIZ, REPS, CgroupMemoria, Planilha, achatar, agora,  # noqa: E402
                   descartar_caches, progresso, rodar_serve)

CONTEXTOS = {"pequeno": (4, 256), "grande": (64, 4096)}
SWAPFILE = "/var/tmp/genresearch.swap"


def parte_a():
    plan = Planilha("c5a_corpus_contexto.csv")
    for corpus in ("S", "M", "L"):
        for modo in ("read", "mmap"):
            for ctx, (k, maxtok) in CONTEXTOS.items():
                for rep in range(1, REPS + 1):
                    rot = f"c5a_{corpus}_{modo}_{ctx}_r{rep}"
                    cfg = {"indice": f"index/{corpus}", "saida": "results/raw/c5", "rotulo": rot,
                           "modo_io": modo, "trabalhadores": 2, "produtores": 2,
                           "requisicoes": 60, "capacidade_fila": 16, "timeout_put": 30.0,
                           "carga": "distinta", "cache_tam": 0, "top_k": k,
                           "max_tokens_contexto": maxtok, "seed": 300 + rep}
                    cod, s, out, dt = rodar_serve(cfg)
                    linha = {"corpus": corpus, "modo": modo, "contexto": ctx, "top_k": k,
                             "max_tokens": maxtok, "rep": rep, "codigo": cod, "horario": agora()}
                    if s:
                        linha.update(achatar(s))
                    plan.add(linha)
                progresso(f"C5a {corpus} {modo} {ctx} ok")


def parte_b():
    plan = Planilha("c5b_lote_ingestao.csv")
    for lote in (256, 4096, 65536):
        for rep in range(1, REPS + 1):
            dest = os.path.join("index", f"M_lote{lote}")
            js = os.path.join("results", "raw", "c5", f"c5b_lote{lote}_r{rep}.json")
            p = subprocess.run([PY, "-m", "genresearch", "ingest", "--corpus", "data/M",
                                "--indice", dest, "--lote", str(lote), "--json", js],
                               cwd=RAIZ, capture_output=True, text=True, timeout=600)
            r = json.loads(p.stdout.strip().splitlines()[-1])
            r.update({"lote_cfg": lote, "rep": rep, "horario": agora()})
            plan.add(r)
        shutil.rmtree(os.path.join(RAIZ, dest), ignore_errors=True)
        progresso(f"C5b lote={lote} ok")


def ativar_swap(mb=2048):
    try:
        if not os.path.exists(SWAPFILE):
            subprocess.run(["fallocate", "-l", f"{mb}M", SWAPFILE], check=True)
            os.chmod(SWAPFILE, 0o600)
            subprocess.run(["mkswap", SWAPFILE], check=True, capture_output=True)
        subprocess.run(["swapon", SWAPFILE], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError) as e:
        progresso(f"swap indisponivel: {e}")
        return False


def desativar_swap():
    subprocess.run(["swapoff", SWAPFILE], capture_output=True)
    try:
        os.remove(SWAPFILE)
    except OSError:
        pass


def parte_c():
    plan = Planilha("c5c_cgroup.csv")
    vm = open(os.path.join(RAIZ, "results", "evidence", "vmstat_c5c.txt"), "w")
    vmp = subprocess.Popen(["vmstat", "-t", "1"], stdout=vm, stderr=subprocess.STDOUT)
    swap_ok = ativar_swap()
    casos = [("mmap", None, False), ("mmap", 160, False), ("mmap", 96, False), ("mmap", 64, False),
             ("read", None, False), ("read", 384, False), ("read", 192, False)]
    if swap_ok:
        casos += [("read", 256, True), ("read", 192, True)]
    try:
        for modo, lim, swap in casos:
            for rep in range(1, REPS + 1):
                rot = f"c5c_{modo}_{lim or 'sem'}_{'swap' if swap else 'noswap'}_r{rep}"
                cfg = {"indice": "index/L", "saida": "results/raw/c5", "rotulo": rot,
                       "modo_io": modo, "trabalhadores": 2, "produtores": 2, "requisicoes": 40,
                       "capacidade_fila": 16, "timeout_put": 60.0, "carga": "distinta",
                       "cache_tam": 0, "top_k": 8, "seed": 400 + rep, "intervalo_amostra": 0.1}
                cg = None
                pre = None
                if lim:
                    cg = CgroupMemoria(f"genresearch_{rot}", lim, swap=swap)
                    if not cg.ok:
                        progresso(f"cgroup indisponivel ({getattr(cg, 'erro', '')}); pulando")
                        continue
                    pre = cg.preexec()
                # cache frio antes de cada rodada: no cgroup v1 a pagina de arquivo e cobrada
                # de quem a trouxe para a memoria; sem isso, paginas ja em cache (cobradas do
                # cgroup pai) escapariam do limite
                descartar_caches()
                cod, s, out, dt = rodar_serve(cfg, timeout=420, preexec=pre)
                linha = {"modo": modo, "limite_mb": lim or 0, "swap": int(swap), "rep": rep,
                         "codigo": cod, "duracao_proc_s": dt, "horario": agora(),
                         "oom_kill": int(cod == -9)}
                if cg:
                    linha.update({"cg." + k: v for k, v in cg.estatisticas().items()})
                    cg.remover()
                if s:
                    linha.update(achatar(s))
                else:
                    linha["saida"] = out[-300:].replace("\n", " ")
                plan.add(linha)
            progresso(f"C5c {modo} lim={lim} swap={swap} ok")
    finally:
        if swap_ok:
            desativar_swap()
        vmp.terminate()
        vm.close()


if __name__ == "__main__":
    partes = sys.argv[1:] or ["a", "b", "c"]
    if "a" in partes:
        parte_a()
    if "b" in partes:
        parte_b()
    if "c" in partes:
        parte_c()
