"""Cache compartilhado de respostas com politica LRU ou FIFO.

modo="none":        sem exclusao mutua (falha controlada). A janela entre ler e
                    gravar e ampliada com time.sleep(0) para tornar visiveis
                    atualizacoes perdidas, computacao duplicada e excecoes.
modo="lock":        mutex protege a estrutura; o calculo ocorre fora do lock
                    (nao serializa a geracao), entao ainda pode haver
                    computacao duplicada quando ha erros simultaneos na mesma chave.
modo="singleflight": mutex + um Event por chave em calculo; quem chega depois
                    espera o primeiro terminar. Elimina a duplicacao.
capacidade=0 desativa o cache.
"""
import collections
import threading
import time


class SharedCache:
    def __init__(self, capacidade=64, politica="lru", modo="lock"):
        self.capacidade = capacidade
        self.politica = politica
        self.modo = modo
        self.dados = collections.OrderedDict()
        self.lock = threading.Lock()
        self.em_calculo = {}
        self.st = {"acertos": 0, "erros": 0, "remocoes": 0, "insercoes": 0,
                   "duplicados": 0, "excecoes": 0, "economia_s": 0.0, "esperas_sf": 0}
        self.computados = collections.Counter()  # chave -> vezes calculada

    # ----------------------------------------------------------------- unsafe
    def _inc_unsafe(self, campo, v=1):
        atual = self.st[campo]
        time.sleep(0)  # janela de corrida ampliada de proposito
        self.st[campo] = atual + v

    def _get_unsafe(self, chave):
        try:
            item = self.dados.get(chave)
            if item is not None and self.politica == "lru":
                self.dados.move_to_end(chave)
            return item
        except (KeyError, RuntimeError):
            self.st["excecoes"] += 1
            return None

    def _put_unsafe(self, chave, valor, custo):
        try:
            if chave in self.dados:
                self._inc_unsafe("duplicados")
            self.dados[chave] = (valor, custo)
            self._inc_unsafe("insercoes")
            while len(self.dados) > self.capacidade:
                self.dados.popitem(last=False)
                self._inc_unsafe("remocoes")
        except (KeyError, RuntimeError):
            self.st["excecoes"] += 1

    # ------------------------------------------------------------------- safe
    def _get_locked(self, chave):
        item = self.dados.get(chave)
        if item is not None and self.politica == "lru":
            self.dados.move_to_end(chave)
        return item

    def _put_locked(self, chave, valor, custo):
        if chave in self.dados:
            self.st["duplicados"] += 1
        self.dados[chave] = (valor, custo)
        self.st["insercoes"] += 1
        while len(self.dados) > self.capacidade:
            self.dados.popitem(last=False)
            self.st["remocoes"] += 1

    # ---------------------------------------------------------------- publico
    def obter_ou_calcular(self, chave, calcular):
        """Retorna (valor, acerto: bool). calcular() -> valor."""
        if self.capacidade <= 0:
            with self.lock:
                self.st["erros"] += 1
            valor, _ = self._calcular(chave, calcular)
            return valor, False

        if self.modo == "none":
            item = self._get_unsafe(chave)
            if item is not None:
                self._inc_unsafe("acertos")
                self._inc_unsafe("economia_s", item[1])
                return item[0], True
            self._inc_unsafe("erros")
            valor, custo = self._calcular(chave, calcular)
            self._put_unsafe(chave, valor, custo)
            return valor, False

        if self.modo == "lock":
            with self.lock:
                item = self._get_locked(chave)
                if item is not None:
                    self.st["acertos"] += 1
                    self.st["economia_s"] += item[1]
                    return item[0], True
                self.st["erros"] += 1
            valor, custo = self._calcular(chave, calcular)
            with self.lock:
                self._put_locked(chave, valor, custo)
            return valor, False

        # singleflight
        while True:
            with self.lock:
                item = self._get_locked(chave)
                if item is not None:
                    self.st["acertos"] += 1
                    self.st["economia_s"] += item[1]
                    return item[0], True
                ev = self.em_calculo.get(chave)
                if ev is None:
                    ev = threading.Event()
                    self.em_calculo[chave] = ev
                    self.st["erros"] += 1
                    dono = True
                else:
                    self.st["esperas_sf"] += 1
                    dono = False
            if dono:
                try:
                    valor, custo = self._calcular(chave, calcular)
                    with self.lock:
                        self._put_locked(chave, valor, custo)
                    return valor, False
                finally:
                    with self.lock:
                        self.em_calculo.pop(chave, None)
                    ev.set()
            ev.wait()  # outro thread calcula; depois tenta de novo (normalmente acerta)

    def _calcular(self, chave, calcular):
        t0 = time.perf_counter()
        valor = calcular()
        custo = time.perf_counter() - t0
        with self.lock:
            self.computados[chave] += 1
        return valor, custo

    def estatisticas(self):
        with self.lock:
            s = dict(self.st)
            s["tamanho"] = len(self.dados)
            s["calculos"] = sum(self.computados.values())
            s["calculos_redundantes"] = sum(v - 1 for v in self.computados.values() if v > 1)
        tot = s["acertos"] + s["erros"]
        s["taxa_acerto"] = s["acertos"] / tot if tot else 0.0
        s["capacidade"] = self.capacidade
        s["politica"] = self.politica
        s["modo"] = self.modo
        return s
