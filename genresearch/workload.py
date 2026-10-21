"""Geracao deterministica de consultas para os experimentos.

repetida:  conjunto pequeno de consultas sorteadas com pesos tipo Zipf
parafrase: mesmas consultas-base reescritas (ordem, caixa, pontuacao, stopwords)
distinta:  toda consulta e unica (combinacoes diferentes de termos)
mista:     metade repetida, metade distinta
"""
import random

from .corpus import COMUNS, termos, topicos

PREFIXOS = ["como", "qual o papel de", "explique", "o que e", "por que", "quando usar"]


def _base(rng):
    tp = rng.choice(topicos())
    return tp, rng.sample(termos(tp), 3)


def gerar_consultas(tipo, n, seed=11, pool=24):
    rng = random.Random(seed)
    bases = []
    vistos = set()
    while len(bases) < pool:
        tp, ws = _base(rng)
        k = tuple(sorted(ws))
        if k not in vistos:
            vistos.add(k)
            bases.append(ws)
    pesos = [1.0 / (i + 1) for i in range(pool)]

    def zipf():
        return rng.choices(bases, weights=pesos, k=1)[0]

    def render(ws, variar=False):
        ws = list(ws)
        if variar:
            rng.shuffle(ws)
            pre = rng.choice(PREFIXOS)
            txt = f"{pre} {' e '.join(ws)}"
            if rng.random() < 0.5:
                txt = txt.upper()
            return txt + rng.choice(["?", "?!", ".", ""])
        return "como " + " e ".join(ws) + "?"

    out = []
    unicos = set()
    for i in range(n):
        modo = tipo
        if tipo == "mista":
            modo = "repetida" if i % 2 == 0 else "distinta"
        if modo == "repetida":
            out.append(render(zipf()))
        elif modo == "parafrase":
            out.append(render(zipf(), variar=True))
        elif modo == "distinta":
            while True:
                tp = rng.choice(topicos())
                ws = rng.sample(termos(tp), 3) + [rng.choice(COMUNS[20:])]
                k = tuple(sorted(ws))
                if k not in unicos and k not in vistos:
                    unicos.add(k)
                    break
            out.append(render(ws))
        else:
            raise ValueError(f"carga desconhecida: {tipo}")
    return out
