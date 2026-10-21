"""CLI do GenResearch-Servidor.

  python -m genresearch corpus  --docs 5000 --saida data/M
  python -m genresearch ingest  --corpus data/M --indice index/M [--lote 4096]
  python -m genresearch serve   --indice index/M --saida results/raw/teste [opcoes]
"""
import argparse
import dataclasses
import json
import os
import sys

from . import corpus as corpus_mod
from .ingest import ingerir
from .logger import EventLogger
from .server import Config, executar
from .store import IndiceIndisponivel


def main(argv=None):
    ap = argparse.ArgumentParser(prog="genresearch")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("corpus", help="gera corpus sintetico")
    c.add_argument("--docs", type=int, required=True)
    c.add_argument("--saida", required=True)
    c.add_argument("--seed", type=int, default=42)

    g = sub.add_parser("ingest", help="ingere corpus e grava indice")
    g.add_argument("--corpus", required=True)
    g.add_argument("--indice", required=True)
    g.add_argument("--lote", type=int, default=4096)
    g.add_argument("--dim", type=int, default=256)
    g.add_argument("--tamanho-trecho", type=int, default=400)
    g.add_argument("--injetar-ausentes", type=int, default=0,
                   help="acrescenta N caminhos inexistentes (falha controlada C6)")
    g.add_argument("--log", default=None)
    g.add_argument("--json", default=None, help="grava resumo da ingestao")

    s = sub.add_parser("serve", help="executa uma carga no servidor")
    for f in dataclasses.fields(Config):
        nome = "--" + f.name.replace("_", "-")
        if f.name in ("indice", "saida"):
            s.add_argument(nome, required=True)
        else:
            s.add_argument(nome, type=type(f.default), default=f.default)
    s.add_argument("--reconstruir-se-ausente", default="",
                   help="pasta do corpus para reconstruir o indice se estiver indisponivel")
    s.add_argument("--quiet", action="store_true")

    a = ap.parse_args(argv)
    if a.cmd == "corpus":
        print(json.dumps(corpus_mod.gerar_corpus(a.saida, a.docs, a.seed)))
        return 0
    if a.cmd == "ingest":
        lg = EventLogger(a.log) if a.log else None
        extras = [os.path.join(a.corpus, "docs", f"ausente_{i}.txt")
                  for i in range(a.injetar_ausentes)]
        r = ingerir(a.corpus, a.indice, a.dim, a.tamanho_trecho, lote=a.lote, logger=lg,
                    arquivos_extras=extras)
        if lg:
            lg.fechar()
        if a.json:
            os.makedirs(os.path.dirname(a.json) or ".", exist_ok=True)
            with open(a.json, "w") as f:
                json.dump(r, f, indent=2)
        print(json.dumps(r))
        return 0
    if a.cmd == "serve":
        kw = {f.name: getattr(a, f.name) for f in dataclasses.fields(Config)}
        cfg = Config(**kw)
        try:
            r = executar(cfg)
        except IndiceIndisponivel as e:
            print(json.dumps({"erro": "indice_indisponivel", "msg": str(e)}))
            if not a.reconstruir_se_ausente:
                return 2
            print(json.dumps({"recuperacao": "reconstruindo indice", "corpus": a.reconstruir_se_ausente}))
            ingerir(a.reconstruir_se_ausente, cfg.indice)
            r = executar(cfg)
        if not a.quiet:
            print(json.dumps({k: r[k] for k in ("rotulo", "wall_s", "vazao_rps")} |
                             {"p95_ms": r["lat_total"]["p95"] * 1000,
                              "hit": r["cache"]["taxa_acerto"], "rss_pico_mb": r["memoria"]["rss_pico_mb"]}))
        return 0


if __name__ == "__main__":
    sys.exit(main())
