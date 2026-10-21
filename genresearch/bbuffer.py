"""Buffer limitado (produtor/consumidor) com semaforos empty/full e mutex.

empty: vagas livres (inicia em capacidade); full: itens disponiveis (inicia em 0);
mutex: protege a estrutura interna (deque) e as estatisticas.
put/get aceitam timeout para que fila cheia ou vazia gere erro controlado
em vez de bloqueio indefinido.
"""
import collections
import threading
import time


class BoundedBuffer:
    def __init__(self, capacidade):
        if capacidade < 1:
            raise ValueError("capacidade deve ser >= 1")
        self.capacidade = capacidade
        self._buf = collections.deque()
        self.empty = threading.Semaphore(capacidade)
        self.full = threading.Semaphore(0)
        self.mutex = threading.Lock()
        self.st = {"puts": 0, "gets": 0, "rejeitados": 0, "tam_max": 0, "soma_tam": 0,
                   "amostras_tam": 0, "espera_put_s": 0.0, "espera_get_s": 0.0,
                   "puts_bloqueados": 0, "gets_bloqueados": 0, "gets_timeout": 0}

    @staticmethod
    def _acquire(sem, timeout):
        if timeout is None:
            return sem.acquire()
        if timeout <= 0:
            return sem.acquire(blocking=False)
        return sem.acquire(timeout=timeout)

    def put(self, item, timeout=None):
        t0 = time.perf_counter()
        bloqueou = not self.empty.acquire(blocking=False)
        if bloqueou and not self._acquire(self.empty, timeout):
            with self.mutex:
                self.st["rejeitados"] += 1
                self.st["espera_put_s"] += time.perf_counter() - t0
                self.st["puts_bloqueados"] += 1
            return False
        espera = time.perf_counter() - t0
        with self.mutex:
            self._buf.append(item)
            n = len(self._buf)
            s = self.st
            s["puts"] += 1
            s["espera_put_s"] += espera
            s["puts_bloqueados"] += int(bloqueou)
            s["tam_max"] = max(s["tam_max"], n)
            s["soma_tam"] += n
            s["amostras_tam"] += 1
        self.full.release()
        return True

    def get(self, timeout=None):
        t0 = time.perf_counter()
        bloqueou = not self.full.acquire(blocking=False)
        if bloqueou and not self._acquire(self.full, timeout):
            with self.mutex:
                self.st["gets_timeout"] += 1
                self.st["espera_get_s"] += time.perf_counter() - t0
                self.st["gets_bloqueados"] += 1
            raise TimeoutError("fila vazia")
        espera = time.perf_counter() - t0
        with self.mutex:
            item = self._buf.popleft()
            n = len(self._buf)
            s = self.st
            s["gets"] += 1
            s["espera_get_s"] += espera
            s["gets_bloqueados"] += int(bloqueou)
            s["soma_tam"] += n
            s["amostras_tam"] += 1
        self.empty.release()
        return item

    def tamanho(self):
        with self.mutex:
            return len(self._buf)

    def estatisticas(self):
        with self.mutex:
            s = dict(self.st)
        s["tam_medio"] = s["soma_tam"] / s["amostras_tam"] if s["amostras_tam"] else 0.0
        s["capacidade"] = self.capacidade
        return s
