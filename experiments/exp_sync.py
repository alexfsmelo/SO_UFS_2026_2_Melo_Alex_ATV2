"""Parte D: sincronizacao e falhas controladas.

D1 atualizacao perdida em contador compartilhado (sem/ com mutex)
D2 computacao duplicada no cache (none / lock / singleflight), micro e no servidor
D3 log intercalado (fragmentado sem lock / linha unica com lock), micro e no servidor
D4 produtor e consumidor bloqueados no buffer limitado
D5 espera circular (deadlock) em processo isolado com timeout e recuperacao
D6 starvation de escritor em trava leitores/escritor com preferencia a leitores
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import PY, RAIZ, REPS, Planilha, achatar, agora, progresso, rodar_serve  # noqa: E402

sys.path.insert(0, RAIZ)
from genresearch.cache import SharedCache  # noqa: E402
from genresearch.logger import EventLogger, validar_log  # noqa: E402


# ------------------------------------------------------------------ D1
def contador(modo, threads=8, n=5000):
    estado = {"v": 0}
    lock = threading.Lock()
    barreira = threading.Barrier(threads)

    def inc():
        barreira.wait()
        for _ in range(n):
            if modo == "lock":
                with lock:  # mesma janela, mas protegida
                    v = estado["v"]
                    time.sleep(0)
                    estado["v"] = v + 1
            elif modo == "sem_lock_janela":
                v = estado["v"]
                time.sleep(0)  # cede a CPU entre ler e gravar
                estado["v"] = v + 1
            else:  # sem_lock: leitura-modificacao-escrita sem pausa artificial
                v = estado["v"]
                estado["v"] = v + 1
    ts = [threading.Thread(target=inc) for _ in range(threads)]
    t0 = time.perf_counter()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    esperado = threads * n
    return {"esperado": esperado, "obtido": estado["v"], "perdidas": esperado - estado["v"],
            "tempo_s": time.perf_counter() - t0}


# ------------------------------------------------------------------ D2
def cache_duplicado(modo, threads=8, rodadas=50):
    redund = 0
    exc = 0
    t0 = time.perf_counter()
    for r in range(rodadas):
        c = SharedCache(16, "lru", modo)
        barreira = threading.Barrier(threads)

        def cliente():
            barreira.wait()
            c.obter_ou_calcular("mesma-consulta", lambda: (time.sleep(0.01), "resp")[1])
        ts = [threading.Thread(target=cliente) for _ in range(threads)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        st = c.estatisticas()
        redund += st["calculos_redundantes"]
        exc += st["excecoes"]
    return {"rodadas": rodadas, "threads": threads, "calculos_redundantes": redund,
            "redundantes_por_rodada": redund / rodadas, "excecoes": exc,
            "tempo_s": time.perf_counter() - t0}


# ------------------------------------------------------------------ D3
def log_intercalado(modo, threads=8, linhas=300):
    d = tempfile.mkdtemp()
    caminho = os.path.join(d, "log.jsonl")
    lg = EventLogger(caminho, modo)
    barreira = threading.Barrier(threads)

    def escrever(i):
        barreira.wait()
        for j in range(linhas):
            lg.log("consulta", req=i * 10000 + j, texto="x" * 40)
    ts = [threading.Thread(target=escrever, args=(i,), name=f"w{i}") for i in range(threads)]
    t0 = time.perf_counter()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    lg.fechar()
    v = validar_log(caminho)
    exemplo = ""
    if v["invalidas"]:
        with open(caminho, "rb") as f:
            for linha in f:
                try:
                    json.loads(linha)
                except ValueError:
                    exemplo = linha[:120].decode("utf-8", "replace")
                    break
    v.update({"esperadas": threads * linhas, "tempo_s": time.perf_counter() - t0,
              "exemplo_corrompido": exemplo})
    return v


# ------------------------------------------------------------------ D6
class RWLockLeitores:
    """Preferencia a leitores: escritor so entra quando nao ha leitores."""

    def __init__(self, preferir_escritor=False):
        self.cond = threading.Condition()
        self.leitores = 0
        self.escrevendo = False
        self.escritores_esperando = 0
        self.preferir_escritor = preferir_escritor

    def ler_inicio(self):
        with self.cond:
            while self.escrevendo or (self.preferir_escritor and self.escritores_esperando):
                self.cond.wait()
            self.leitores += 1

    def ler_fim(self):
        with self.cond:
            self.leitores -= 1
            if self.leitores == 0:
                self.cond.notify_all()

    def escrever_inicio(self):
        with self.cond:
            self.escritores_esperando += 1
            while self.escrevendo or self.leitores > 0:
                self.cond.wait()
            self.escritores_esperando -= 1
            self.escrevendo = True

    def escrever_fim(self):
        with self.cond:
            self.escrevendo = False
            self.cond.notify_all()


def starvation(preferir_escritor, leitores=6, duracao=1.5, limite_espera=1.5):
    rw = RWLockLeitores(preferir_escritor)
    fim = time.perf_counter() + duracao
    leituras = [0]
    espera_escritor = []

    def leitor():
        while time.perf_counter() < fim:
            rw.ler_inicio()
            time.sleep(0.004)
            leituras[0] += 1
            rw.ler_fim()

    def escritor():
        time.sleep(0.05)
        for _ in range(5):
            t0 = time.perf_counter()
            rw.escrever_inicio()
            espera_escritor.append(time.perf_counter() - t0)
            time.sleep(0.002)
            rw.escrever_fim()
            if time.perf_counter() > fim:
                break
    ts = [threading.Thread(target=leitor) for _ in range(leitores)]
    te = threading.Thread(target=escritor)
    for t in ts:
        t.start()
    te.start()
    for t in ts:
        t.join()
    te.join(timeout=limite_espera)
    return {"leituras": leituras[0], "escritas": len(espera_escritor),
            "espera_escritor_max_s": max(espera_escritor) if espera_escritor else None,
            "espera_escritor_media_s": (sum(espera_escritor) / len(espera_escritor))
            if espera_escritor else None}


# ------------------------------------------------------------------ D5
def deadlock(modo, limite=3.0):
    p = subprocess.Popen([PY, os.path.join(RAIZ, "experiments", "deadlock_demo.py"), modo],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    primeira = json.loads(p.stdout.readline())
    pid = primeira["pid"]
    t0 = time.perf_counter()
    estados = ""
    try:
        so, se = p.communicate(timeout=limite)
        res = json.loads(so.strip().splitlines()[-1])
        res.update({"encerrado_pelo_pai": 0, "codigo": p.returncode})
    except subprocess.TimeoutExpired:
        # evidencia: estado e canal de espera de cada thread antes de encerrar
        linhas = []
        for tid in sorted(os.listdir(f"/proc/{pid}/task")):
            try:
                comm = open(f"/proc/{pid}/task/{tid}/comm").read().strip()
                st = open(f"/proc/{pid}/task/{tid}/stat").read().split(") ")[1].split()[0]
                wchan = open(f"/proc/{pid}/task/{tid}/wchan").read().strip()
                linhas.append(f"tid={tid} comm={comm} estado={st} wchan={wchan}")
            except OSError:
                pass
        estados = " ; ".join(linhas)
        p.terminate()
        try:
            p.wait(timeout=1)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        res = {"modo": modo, "tempo_s": time.perf_counter() - t0, "encerrado_pelo_pai": 1,
               "codigo": p.returncode, "concluidas": None, "retentativas": None}
    res["threads_no_timeout"] = estados
    return res


def main():
    plan = Planilha("d_sincronizacao.csv")
    for rep in range(1, REPS + 1):
        for modo in ("sem_lock", "sem_lock_janela", "lock"):
            r = contador(modo)
            plan.add({"teste": "D1_contador", "modo": modo, "rep": rep, **r, "horario": agora()})
        for modo in ("none", "lock", "singleflight"):
            r = cache_duplicado(modo)
            plan.add({"teste": "D2_cache_micro", "modo": modo, "rep": rep, **r, "horario": agora()})
        for modo in ("unsafe", "lock"):
            r = log_intercalado(modo)
            plan.add({"teste": "D3_log_micro", "modo": modo, "rep": rep, **r, "horario": agora()})
        for pref in (False, True):
            r = starvation(pref)
            plan.add({"teste": "D6_starvation", "modo": "pref_escritor" if pref else "pref_leitores",
                      "rep": rep, **r, "horario": agora()})
        for modo in ("ingenuo", "timeout", "ordenado"):
            r = deadlock(modo)
            r["concluidas"] = json.dumps(r.get("concluidas"))
            r["retentativas"] = json.dumps(r.get("retentativas"))
            plan.add({"teste": "D5_deadlock", "rep": rep, **r, "horario": agora()})
        progresso(f"D micro rep {rep} ok")

    srv = Planilha("d_servidor.csv")
    casos = [
        ("D2_cache_servidor", {"cache_tam": 64, "cache_modo": "none", "carga": "repetida"}),
        ("D2_cache_servidor", {"cache_tam": 64, "cache_modo": "lock", "carga": "repetida"}),
        ("D2_cache_servidor", {"cache_tam": 64, "cache_modo": "singleflight", "carga": "repetida"}),
        ("D3_log_servidor", {"log_modo": "unsafe"}),
        ("D3_log_servidor", {"log_modo": "lock"}),
        ("D4_consumidor_bloqueado", {"chegada_ms": 40.0, "trabalhadores": 4, "capacidade_fila": 8}),
        ("D4_produtor_bloqueado", {"chegada_ms": 0.0, "trabalhadores": 1, "capacidade_fila": 2,
                                   "timeout_put": 30.0}),
    ]
    for rep in range(1, REPS + 1):
        for teste, extra in casos:
            rot = f"{teste}_{'_'.join(str(v) for v in extra.values())}_r{rep}"
            cfg = {"indice": "index/M", "saida": "results/raw/d", "rotulo": rot,
                   "trabalhadores": 4, "produtores": 2, "requisicoes": 120,
                   "capacidade_fila": 16, "timeout_put": 30.0, "carga": "distinta",
                   "seed": 500 + rep}
            cfg.update(extra)
            cod, s, out, dt = rodar_serve(cfg)
            linha = {"teste": teste, **{f"cfg_{k}": v for k, v in extra.items()}, "rep": rep,
                     "codigo": cod, "horario": agora()}
            if s:
                linha.update(achatar(s))
            srv.add(linha)
        progresso(f"D servidor rep {rep} ok")


if __name__ == "__main__":
    main()
