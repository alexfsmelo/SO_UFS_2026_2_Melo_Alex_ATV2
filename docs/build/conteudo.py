"""Monta docs/build/conteudo.json (texto do relatorio) a partir dos resultados.
Os numeros vem de results/tables/*.csv e numeros.json; nada e digitado a mao."""
import json
import os

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
TAB = os.path.join(RAIZ, "results", "tables")
FIG = "../../results/figures"
N = json.load(open(os.path.join(TAB, "numeros.json")))
REPO = "https://github.com/alexfsmelo/SO_UFS_2026_2_Melo_Alex_ATV2"
VIDEO = os.environ.get("VIDEO_URL", "PREENCHER_URL_DO_VIDEO")


def t(nome):
    return pd.read_csv(os.path.join(TAB, nome + ".csv"))


def f(x, n=1):
    s = f"{x:,.{n}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def i(x):
    return f(x, 0)


def pct(x, n=0):
    return f(100 * x, n) + "%"


B = []


def h1(x): B.append({"h1": x})
def h2(x): B.append({"h2": x})
def p(x): B.append({"p": x})
def bl(*xs): B.append({"bullets": list(xs)})
def fig(arq, cap, cm=16.5): B.append({"fig": f"{FIG}/{arq}", "cap": cap, "cm": cm})
def tab(cols, rows, cap, pesos=None, fonte=16, esquerda=()):
    B.append({"table": {"cols": cols, "rows": rows, "pesos": pesos, "fonte": fonte,
                        "esquerda": list(esquerda)}, "cap": cap})


exec(open(os.path.join(AQUI, "secoes.py"), encoding="utf-8").read())

json.dump({"titulo_doc": "AV2 Sistemas Operacionais: GenResearch-Servidor", "blocos": B},
          open(os.path.join(AQUI, "conteudo.json"), "w"), ensure_ascii=False, indent=1)
print("blocos:", len(B))
