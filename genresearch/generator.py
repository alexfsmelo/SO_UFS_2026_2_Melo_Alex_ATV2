"""Etapa de resposta: geracao simulada (padrao) ou por Ollama local (opcional).

O gerador simulado modela o custo de um servidor de inferencia:
  espera = tokens_contexto / prefill_tps + tokens_saida / decode_tps
A espera e feita com time.sleep, como uma thread bloqueada aguardando a
resposta HTTP do Ollama (E/S). cpu_ms acrescenta trabalho de CPU em Python
puro, que segura o GIL, para comparar cargas limitadas por E/S e por CPU.
taxa_falha injeta falhas deterministicas de "servico externo".
"""
import json
import random
import time
import urllib.error
import urllib.request


class FalhaGeracao(Exception):
    pass


class GeradorSimulado:
    def __init__(self, prefill_tps=20000.0, decode_tps=400.0, tokens_saida=16,
                 cpu_ms=0.0, taxa_falha=0.0, seed=7):
        self.prefill_tps = prefill_tps
        self.decode_tps = decode_tps
        self.tokens_saida = tokens_saida
        self.cpu_ms = cpu_ms
        self.taxa_falha = taxa_falha
        self.seed = seed
        self.nome = "simulado"
        self.iteracoes = self._calibrar() if cpu_ms > 0 else 0

    @staticmethod
    def _bloco():
        x = 0
        for i in range(200):
            x += i * i
        return x

    def _calibrar(self):
        """Mede quantos blocos cabem em cpu_ms com uma thread so. O trabalho passa a ser
        uma quantidade FIXA de instrucoes (nao um tempo de parede), entao, com o GIL,
        duas threads levam o dobro do tempo cada uma."""
        n = 0
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 0.05:
            self._bloco()
            n += 1
        por_ms = n / ((time.perf_counter() - t0) * 1000.0)
        return max(1, int(por_ms * self.cpu_ms))

    def _queimar_cpu(self):
        x = 0
        for _ in range(self.iteracoes):
            x += self._bloco()
        return x

    def gerar(self, consulta, tokens_contexto, req_id=0, tentativa=0):
        espera = 0.0
        if self.prefill_tps > 0:
            espera += tokens_contexto / self.prefill_tps
        if self.decode_tps > 0:
            espera += self.tokens_saida / self.decode_tps
        if espera > 0:
            time.sleep(espera)
        if self.cpu_ms > 0:
            self._queimar_cpu()
        if self.taxa_falha > 0:
            rng = random.Random(self.seed * 1_000_003 + req_id * 31 + tentativa)
            if rng.random() < self.taxa_falha:
                raise FalhaGeracao(f"servico externo indisponivel (req {req_id}, tentativa {tentativa})")
        return f"[simulado] resposta para '{consulta[:48]}' usando {tokens_contexto} tokens de contexto"


class GeradorOllama:
    def __init__(self, modelo="deepseek-r1:1.5b", url="http://localhost:11434",
                 tokens_saida=32, timeout=120.0):
        self.modelo = modelo
        self.url = url.rstrip("/") + "/api/generate"
        self.tokens_saida = tokens_saida
        self.timeout = timeout
        self.nome = f"ollama:{modelo}"

    def gerar(self, consulta, tokens_contexto, req_id=0, tentativa=0, contexto=""):
        prompt = f"Contexto:\n{contexto}\n\nPergunta: {consulta}\nResponda em uma frase."
        corpo = json.dumps({"model": self.modelo, "prompt": prompt, "stream": False,
                            "options": {"num_predict": self.tokens_saida}}).encode()
        req = urllib.request.Request(self.url, data=corpo,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = json.loads(r.read())
            return resp.get("response", "")[:200]
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise FalhaGeracao(f"ollama indisponivel: {e}") from e
