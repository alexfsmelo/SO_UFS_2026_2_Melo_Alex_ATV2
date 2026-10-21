"""GenResearch-Servidor: produtores -> fila limitada -> trabalhadores (threads).

Cada trabalhador: retira requisicao, consulta o cache compartilhado e, em caso
de erro de cache, faz embedding da consulta, busca no indice, monta contexto
limitado e chama o gerador. Tudo e registrado em log JSONL e em CSVs.
"""
import csv
import json
import os
import random
import threading
import time
from dataclasses import asdict, dataclass

from . import metrics
from .bbuffer import BoundedBuffer
from .cache import SharedCache
from .embed import HashEmbedder, chave_normalizada
from .generator import FalhaGeracao, GeradorOllama, GeradorSimulado
from .logger import EventLogger, validar_log
from .store import VectorStore
from .workload import gerar_consultas

PARAR = object()


@dataclass
class Config:
    indice: str
    saida: str
    rotulo: str = "execucao"
    modo_io: str = "mmap"          # read | mmap
    trabalhadores: int = 2
    produtores: int = 2
    requisicoes: int = 120
    capacidade_fila: int = 16
    timeout_put: float = 1.0       # s; fila cheia por mais tempo -> rejeicao
    retentativas_put: int = 3
    chegada_ms: float = 0.0        # intervalo entre envios de cada produtor
    carga: str = "distinta"        # repetida | parafrase | distinta | mista
    cache_tam: int = 0
    cache_politica: str = "lru"
    cache_modo: str = "lock"       # lock | none | singleflight
    log_modo: str = "lock"         # lock | unsafe
    top_k: int = 8
    max_tokens_contexto: int = 512
    backend: str = "simulado"      # simulado | ollama
    modelo_ollama: str = "deepseek-r1:1.5b"
    url_ollama: str = "http://localhost:11434"
    prefill_tps: float = 20000.0
    decode_tps: float = 400.0
    tokens_saida: int = 16
    cpu_ms: float = 0.0
    taxa_falha: float = 0.0
    retentativas_geracao: int = 2
    intervalo_amostra: float = 0.05
    seed: int = 11


def tokens_aprox(texto):
    return max(1, int(len(texto.split()) * 1.3))


class Servidor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        os.makedirs(cfg.saida, exist_ok=True)
        self.log = EventLogger(os.path.join(cfg.saida, f"{cfg.rotulo}.log.jsonl"), cfg.log_modo)
        self.fila = BoundedBuffer(cfg.capacidade_fila)
        self.cache = SharedCache(cfg.cache_tam, cfg.cache_politica, cfg.cache_modo)
        self.emb = HashEmbedder()
        if cfg.backend == "ollama":
            self.gerador = GeradorOllama(cfg.modelo_ollama, cfg.url_ollama,
                                         tokens_saida=cfg.tokens_saida)
        else:
            self.gerador = GeradorSimulado(cfg.prefill_tps, cfg.decode_tps, cfg.tokens_saida,
                                           cfg.cpu_ms, cfg.taxa_falha, cfg.seed)
        self.resultados = []
        self.res_lock = threading.Lock()
        self.aceitos = []
        self.descartados = 0
        self.ocupados = 0
        self.ocup_lock = threading.Lock()
        self.tempo_ocupado = {}
        self.store = None

    # ------------------------------------------------------------- produtores
    def produtor(self, pid, consultas):
        metrics.nomear_thread(f"produtor-{pid}")
        for j, q in enumerate(consultas):
            req = {"id": pid * 1_000_000 + j, "produtor": pid, "consulta": q,
                   "t_criacao": time.perf_counter(), "tent_put": 0}
            ok = False
            for tent in range(self.cfg.retentativas_put + 1):
                req["tent_put"] = tent
                if self.fila.put(req, timeout=self.cfg.timeout_put):
                    ok = True
                    break
                self.log.log("fila_cheia", req=req["id"], tentativa=tent)
                time.sleep(0.002 * (2 ** tent))
            if ok:
                with self.res_lock:
                    self.aceitos.append(req["id"])
            else:
                with self.res_lock:
                    self.descartados += 1
                self.log.log("requisicao_descartada", req=req["id"])
            if self.cfg.chegada_ms > 0:
                time.sleep(self.cfg.chegada_ms / 1000.0)

    # ---------------------------------------------------------- trabalhadores
    def _contexto(self, ids):
        partes = []
        tokens = 0
        nbytes = 0
        usados = 0
        for i in ids:
            t = self.store.texto(int(i))
            tk = tokens_aprox(t)
            if tokens + tk > self.cfg.max_tokens_contexto and usados > 0:
                break
            partes.append(t)
            tokens += tk
            nbytes += len(t.encode("utf-8"))
            usados += 1
        return "\n".join(partes), usados, tokens, nbytes

    def _processar(self, req):
        t0 = time.perf_counter()
        qv = self.emb.embed(req["consulta"])
        ids, scores = self.store.buscar(qv, self.cfg.top_k)
        ctx, usados, tokens, nbytes = self._contexto(ids)
        meta = self.store.metadados(ids[:usados])
        t1 = time.perf_counter()
        resposta = None
        tentativas = 0
        erro = ""
        for tent in range(self.cfg.retentativas_geracao + 1):
            tentativas = tent + 1
            try:
                if isinstance(self.gerador, GeradorOllama):
                    resposta = self.gerador.gerar(req["consulta"], tokens, req["id"], tent, ctx)
                else:
                    resposta = self.gerador.gerar(req["consulta"], tokens, req["id"], tent)
                break
            except FalhaGeracao as e:
                erro = str(e)[:100]
                self.log.log("falha_geracao", req=req["id"], tentativa=tent, erro=erro)
                time.sleep(0.005 * (2 ** tent))
        t2 = time.perf_counter()
        topicos = sorted({v[1] for v in meta.values()})
        if resposta is None:
            raise FalhaGeracao(erro)
        return {"resposta": resposta, "trechos": usados, "tokens_ctx": tokens, "bytes_ctx": nbytes,
                "t_recuperacao": t1 - t0, "t_geracao": t2 - t1, "tentativas": tentativas,
                "topicos": "|".join(topicos), "score_top": float(scores[0]) if len(scores) else 0.0}

    def trabalhador(self, wid):
        nome = f"worker-{wid}"
        metrics.nomear_thread(nome)
        ocupado = 0.0
        while True:
            req = self.fila.get()
            if req is PARAR:
                break
            t_deq = time.perf_counter()
            with self.ocup_lock:
                self.ocupados += 1
            status = "ok"
            hit = False
            info = {}
            try:
                chave = chave_normalizada(req["consulta"])
                info, hit = self.cache.obter_ou_calcular(chave, lambda: self._processar(req))
            except FalhaGeracao as e:
                status = "erro_geracao"
                info = {"erro": str(e)[:100]}
            except Exception as e:  # falha inesperada nao derruba o trabalhador
                status = "erro_" + type(e).__name__
                info = {"erro": str(e)[:100]}
                self.log.log("falha", req=req["id"], erro=repr(e)[:120])
            t_fim = time.perf_counter()
            with self.ocup_lock:
                self.ocupados -= 1
            ocupado += t_fim - t_deq
            linha = {
                "id": req["id"], "produtor": req["produtor"], "worker": wid,
                "t_criacao": req["t_criacao"],
                "t_inicio": t_deq, "t_fim": t_fim,
                "espera_fila_s": t_deq - req["t_criacao"],
                "recuperacao_s": 0.0 if hit else info.get("t_recuperacao", 0.0),
                "geracao_s": 0.0 if hit else info.get("t_geracao", 0.0),
                "servico_s": t_fim - t_deq, "total_s": t_fim - req["t_criacao"],
                "cache_hit": int(hit), "trechos": info.get("trechos", 0),
                "tokens_ctx": info.get("tokens_ctx", 0), "bytes_ctx": info.get("bytes_ctx", 0),
                "tentativas": info.get("tentativas", 0), "status": status,
                "tent_put": req["tent_put"],
            }
            with self.res_lock:
                self.resultados.append(linha)
            self.log.log("consulta", req=req["id"], worker=wid, hit=int(hit), status=status,
                         trechos=linha["trechos"], ms=round(linha["total_s"] * 1000, 2))
        with self.res_lock:
            self.tempo_ocupado[wid] = ocupado

    # ------------------------------------------------------------------ run
    def executar(self):
        cfg = self.cfg
        mi0 = metrics.meminfo()
        io0, ru0, st0 = metrics.proc_io(), metrics.rusage(), metrics.status()
        self.log.log("inicio", config=asdict(cfg))
        t_ini = time.perf_counter()
        self.store = VectorStore(cfg.indice, cfg.modo_io)
        t_carga = time.perf_counter() - t_ini
        st_carga = metrics.status()
        self.log.log("indice_carregado", modo=cfg.modo_io, n=self.store.n, t_s=round(t_carga, 4),
                     rss_mb=st_carga.get("VmRSS"))
        consultas = gerar_consultas(cfg.carga, cfg.requisicoes, cfg.seed)
        por_prod = [consultas[i::cfg.produtores] for i in range(cfg.produtores)]
        amostrador = metrics.Amostrador(cfg.intervalo_amostra, self.fila.tamanho,
                                        lambda: self.ocupados)
        amostrador.start()
        t0 = time.perf_counter()
        ws = [threading.Thread(target=self.trabalhador, args=(w,), name=f"worker-{w}")
              for w in range(cfg.trabalhadores)]
        ps = [threading.Thread(target=self.produtor, args=(p, por_prod[p]), name=f"produtor-{p}")
              for p in range(cfg.produtores)]
        for t in ws + ps:
            t.start()
        threads_pico = metrics.status().get("Threads", 0)
        for t in ps:
            t.join()
        for _ in ws:
            self.fila.put(PARAR)
        for t in ws:
            t.join()
        wall = time.perf_counter() - t0
        amostrador.parar()
        io1, ru1, st1, mi1 = metrics.proc_io(), metrics.rusage(), metrics.status(), metrics.meminfo()
        self.log.log("encerramento", processadas=len(self.resultados), wall_s=round(wall, 4))
        self.log.fechar()
        self.store.fechar()
        return self._resumo(wall, t_carga, st_carga, io0, io1, ru0, ru1, st0, st1, mi0, mi1,
                            amostrador.linhas, threads_pico)

    def _resumo(self, wall, t_carga, st_carga, io0, io1, ru0, ru1, st0, st1, mi0, mi1, amostras,
                threads_pico):
        cfg = self.cfg
        R = self.resultados
        ok = [r for r in R if r["status"] == "ok"]
        miss = [r for r in ok if not r["cache_hit"]]
        ids = [r["id"] for r in R]
        aceitos = set(self.aceitos)
        processados = set(ids)
        ordem = sorted(R, key=lambda r: r["t_fim"])
        inversoes = sum(1 for a, b in zip(ordem, ordem[1:]) if b["t_inicio"] < a["t_inicio"])
        logv = validar_log(os.path.join(cfg.saida, f"{cfg.rotulo}.log.jsonl"))
        io = metrics.delta(io0, io1)
        ru = metrics.delta(ru0, ru1)
        util = sum(self.tempo_ocupado.values()) / (wall * cfg.trabalhadores) if wall else 0
        s = {
            "rotulo": cfg.rotulo, "config": asdict(cfg),
            "wall_s": wall, "t_carga_indice_s": t_carga,
            "n_trechos": self.store.n if self.store else 0,
            "vazao_rps": len(ok) / wall if wall else 0,
            "lat_total": metrics.resumo([r["total_s"] for r in ok]),
            "lat_espera_fila": metrics.resumo([r["espera_fila_s"] for r in ok]),
            "lat_recuperacao": metrics.resumo([r["recuperacao_s"] for r in miss]),
            "lat_geracao": metrics.resumo([r["geracao_s"] for r in miss]),
            "lat_servico": metrics.resumo([r["servico_s"] for r in ok]),
            "contexto_trechos_medio": (sum(r["trechos"] for r in miss) / len(miss)) if miss else 0,
            "contexto_tokens_medio": (sum(r["tokens_ctx"] for r in miss) / len(miss)) if miss else 0,
            "contexto_bytes_medio": (sum(r["bytes_ctx"] for r in miss) / len(miss)) if miss else 0,
            "fila": self.fila.estatisticas(),
            "cache": self.cache.estatisticas(),
            "utilizacao_trabalhadores": util,
            "threads_pico": max([a["threads"] for a in amostras] + [threads_pico]),
            "memoria": {
                "rss_inicio_mb": st0.get("VmRSS"), "rss_apos_carga_mb": st_carga.get("VmRSS"),
                "rss_fim_mb": st1.get("VmRSS"), "rss_pico_mb": st1.get("VmHWM"),
                "vsz_fim_mb": st1.get("VmSize"), "vsz_pico_mb": st1.get("VmPeak"),
                "rss_anon_fim_mb": st1.get("RssAnon"), "rss_file_fim_mb": st1.get("RssFile"),
                "swap_fim_mb": st1.get("VmSwap"),
                "swap_pico_mb": max([a["swap_mb"] for a in amostras] + [0]),
                "rss_amostrado_max_mb": max([a["rss_mb"] for a in amostras] + [0]),
                "mem_available_ini_mb": mi0.get("MemAvailable"),
                "mem_available_min_mb": min([a["mem_available_mb"] for a in amostras] +
                                            [mi1.get("MemAvailable", 0)]),
                "minflt": ru.get("minflt", 0), "majflt": ru.get("majflt", 0),
                "utime_s": ru.get("utime", 0), "stime_s": ru.get("stime", 0),
                "nvcsw": ru.get("nvcsw", 0), "nivcsw": ru.get("nivcsw", 0),
            },
            "io": {k: io.get(k, 0) for k in ("rchar", "wchar", "read_bytes", "write_bytes",
                                              "syscr", "syscw")},
            "correcao": {
                "enviadas": cfg.requisicoes, "aceitas": len(aceitos),
                "descartadas_fila_cheia": self.descartados,
                "processadas": len(R), "ok": len(ok),
                "erros": len(R) - len(ok),
                "perdidas": len(aceitos - processados),
                "duplicadas": len(ids) - len(processados),
                "inversoes_ordem_conclusao": inversoes,
                "log": logv,
                "rejeicoes_put": self.fila.estatisticas()["rejeitados"],
                "retentativas_geracao": sum(max(0, r["tentativas"] - 1) for r in miss),
            },
        }
        base = os.path.join(cfg.saida, cfg.rotulo)
        with open(base + ".summary.json", "w") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
        if R:
            with open(base + ".requests.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(R[0].keys()))
                w.writeheader()
                w.writerows(sorted(R, key=lambda r: r["t_inicio"]))
        if amostras:
            with open(base + ".timeseries.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(amostras[0].keys()))
                w.writeheader()
                w.writerows(amostras)
        return s


def executar(cfg: Config):
    random.seed(cfg.seed)
    return Servidor(cfg).executar()
