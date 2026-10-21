"""C6: falhas controladas.
1 arquivo ausente na ingestao; 2 indice indisponivel (ausente, truncado,
reconstrucao); 3 fila saturada; 4 limite de memoria (OOM no cgroup e
recuperacao com mmap); 5 falha de servico externo com e sem retentativas."""
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import (PY, RAIZ, REPS, CgroupMemoria, Planilha, achatar, agora,  # noqa: E402
                   descartar_caches, progresso, rodar_serve)

sys.path.insert(0, RAIZ)
from genresearch.logger import validar_log  # noqa: E402


def cmd(args, timeout=300):
    t0 = time.perf_counter()
    p = subprocess.run([PY, "-m", "genresearch"] + args, cwd=RAIZ, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr, time.perf_counter() - t0


def main():
    plan = Planilha("c6_falhas.csv")
    out = "results/raw/c6"
    os.makedirs(os.path.join(RAIZ, out), exist_ok=True)

    # 1. arquivo ausente
    for rep in range(1, REPS + 1):
        log = f"{out}/c6_ausente_r{rep}.log.jsonl"
        c, so, se, dt = cmd(["ingest", "--corpus", "data/S", "--indice", "index/S_falha",
                             "--injetar-ausentes", "5", "--log", log])
        r = json.loads(so.strip().splitlines()[-1])
        ev = [json.loads(l)["evento"] for l in open(os.path.join(RAIZ, log))]
        plan.add({"caso": "arquivo_ausente", "rep": rep, "codigo": c, "duracao_s": dt,
                  "docs_ok": r["n_docs"], "falhas": r["falhas_leitura"],
                  "eventos_falha_log": ev.count("falha_ingestao"),
                  "resultado": "ingestao concluiu ignorando 5 arquivos", "horario": agora()})
    progresso("C6 arquivo ausente ok")

    # 2. indice indisponivel
    base = os.path.join(RAIZ, "index", "S_falha")
    for rep in range(1, REPS + 1):
        for variante in ("ausente", "truncado", "reconstrucao"):
            alvo = os.path.join(base, "vectors.f32")
            if variante in ("ausente", "reconstrucao"):
                os.remove(alvo)
            else:
                with open(alvo, "r+b") as f:
                    f.truncate(os.path.getsize(alvo) // 2)
            args = ["serve", "--indice", "index/S_falha", "--saida", out,
                    "--rotulo", f"c6_indice_{variante}_r{rep}", "--requisicoes", "20", "--quiet"]
            if variante == "reconstrucao":
                args += ["--reconstruir-se-ausente", "data/S"]
            c, so, se, dt = cmd(args)
            msg = so.strip().splitlines()[0][:160] if so.strip() else se[-160:]
            plan.add({"caso": f"indice_{variante}", "rep": rep, "codigo": c, "duracao_s": dt,
                      "resultado": msg, "horario": agora()})
            if variante != "reconstrucao":
                cmd(["ingest", "--corpus", "data/S", "--indice", "index/S_falha"])
    progresso("C6 indice ok")

    # 3. fila saturada
    for cap, tout, rput in ((2, 0.005, 0), (2, 0.005, 3), (64, 30.0, 0)):
        for rep in range(1, REPS + 1):
            rot = f"c6_fila_cap{cap}_t{tout}_r{rput}_r{rep}"
            cfg = {"indice": "index/M", "saida": out, "rotulo": rot, "trabalhadores": 1,
                   "produtores": 4, "requisicoes": 80, "capacidade_fila": cap,
                   "timeout_put": tout, "retentativas_put": rput, "carga": "distinta",
                   "seed": 600 + rep}
            c, s, o, dt = rodar_serve(cfg)
            linha = {"caso": "fila_saturada", "capacidade": cap, "timeout_put": tout,
                     "retentativas_put": rput, "rep": rep, "codigo": c, "horario": agora()}
            if s:
                linha.update(achatar(s))
            plan.add(linha)
    progresso("C6 fila ok")

    # 4. limite de memoria: read sob 192 MB sem swap -> OOM; recuperacao com mmap
    for rep in range(1, REPS + 1):
        for modo in ("read", "mmap"):
            rot = f"c6_mem_{modo}_r{rep}"
            cg = CgroupMemoria(f"genresearch_{rot}", 192, swap=False)
            if not cg.ok:
                plan.add({"caso": "limite_memoria", "rep": rep, "resultado": "cgroup indisponivel"})
                continue
            cfg = {"indice": "index/L", "saida": out, "rotulo": rot, "modo_io": modo,
                   "requisicoes": 30, "trabalhadores": 2, "carga": "distinta", "seed": 700 + rep}
            descartar_caches()
            c, s, o, dt = rodar_serve(cfg, timeout=300, preexec=cg.preexec())
            linha = {"caso": "limite_memoria", "modo": modo, "limite_mb": 192, "rep": rep,
                     "codigo": c, "duracao_s": dt, "oom_kill": int(c == -9), "horario": agora(),
                     "resultado": "morto por OOM (SIGKILL)" if c == -9 else
                     ("ok" if c == 0 else f"codigo {c}")}
            linha.update({"cg." + k: v for k, v in cg.estatisticas().items()})
            cg.remover()
            if s:
                linha.update(achatar(s))
            plan.add(linha)
    progresso("C6 memoria ok")

    # 5. servico externo
    for taxa in (0.2, 0.5):
        for ret in (0, 2):
            for rep in range(1, REPS + 1):
                rot = f"c6_ext_t{taxa}_ret{ret}_r{rep}"
                cfg = {"indice": "index/M", "saida": out, "rotulo": rot, "trabalhadores": 2,
                       "requisicoes": 100, "carga": "distinta", "taxa_falha": taxa,
                       "retentativas_geracao": ret, "seed": 800 + rep}
                c, s, o, dt = rodar_serve(cfg)
                linha = {"caso": "servico_externo", "taxa_falha": taxa, "retentativas": ret,
                         "rep": rep, "codigo": c, "horario": agora()}
                if s:
                    linha.update(achatar(s))
                plan.add(linha)
    for rep in range(1, REPS + 1):
        rot = f"c6_ollama_off_r{rep}"
        cfg = {"indice": "index/S", "saida": out, "rotulo": rot, "backend": "ollama",
               "requisicoes": 10, "retentativas_geracao": 1, "seed": 900 + rep,
               "url_ollama": "http://127.0.0.1:9"}
        c, s, o, dt = rodar_serve(cfg)
        linha = {"caso": "ollama_indisponivel", "rep": rep, "codigo": c, "horario": agora()}
        if s:
            linha.update(achatar(s))
        plan.add(linha)
    progresso("C6 servico externo ok")
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
