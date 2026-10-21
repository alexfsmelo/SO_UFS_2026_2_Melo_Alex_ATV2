"""Embeddings simulados por hashing (feature hashing), deterministicos.

Nao ha modelo neural: cada token e mapeado para uma posicao e um sinal por
CRC32. O vetor resultante e normalizado (norma L2 = 1), entao o produto
escalar equivale a similaridade de cosseno. Isso preserva o padrao de acesso
a memoria de um indice vetorial real (matriz N x D em float32).
"""
import re
import zlib

import numpy as np

TOKEN_RE = re.compile(r"\w+", re.UNICODE)
STOPWORDS = set("o a os as de do da dos das em no na um uma para com por sobre entre e "
                "que qual quais como quando onde se ao aos pela pelo".split())


def tokenizar(texto):
    return [t for t in TOKEN_RE.findall(texto.lower()) if t not in STOPWORDS]


def chave_normalizada(consulta):
    """Chave do cache: conjunto ordenado de tokens sem stopwords.
    Parafrases com as mesmas palavras (ordem, caixa, pontuacao) colidem."""
    return " ".join(sorted(set(tokenizar(consulta))))


class HashEmbedder:
    def __init__(self, dim=256):
        self.dim = dim
        self._memo = {}  # corrida benigna: dois threads gravam o mesmo valor

    def _feat(self, tok):
        f = self._memo.get(tok)
        if f is None:
            h = zlib.crc32(tok.encode("utf-8"))
            f = (h % self.dim, 1.0 if (h >> 16) & 1 else -1.0)
            self._memo[tok] = f
        return f

    def embed(self, texto):
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in tokenizar(texto):
            i, s = self._feat(tok)
            v[i] += s
        n = float(np.linalg.norm(v))
        if n > 0:
            v /= n
        return v

    def embed_lote(self, textos):
        m = np.zeros((len(textos), self.dim), dtype=np.float32)
        for r, texto in enumerate(textos):
            idx = []
            sig = []
            for tok in tokenizar(texto):
                i, s = self._feat(tok)
                idx.append(i)
                sig.append(s)
            if idx:
                np.add.at(m[r], idx, sig)
        normas = np.linalg.norm(m, axis=1, keepdims=True)
        normas[normas == 0] = 1.0
        m /= normas
        return m
