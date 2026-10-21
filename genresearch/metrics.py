"""Coleta de metricas do processo e do sistema via /proc e getrusage."""
import ctypes
import ctypes.util
import mmap
import os
import resource
import statistics
import threading
import time

_libc = None


def libc():
    global _libc
    if _libc is None:
        _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
    return _libc


def nomear_thread(nome):
    """Define o nome da thread no kernel (visivel em /proc/PID/task/TID/comm e ps -L)."""
    try:
        libc().prctl(15, nome.encode()[:15], 0, 0, 0)  # PR_SET_NAME
    except Exception:
        pass


def _kv_file(path):
    out = {}
    try:
        with open(path) as f:
            for linha in f:
                if ":" in linha:
                    k, v = linha.split(":", 1)
                    out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def status(pid="self"):
    """VmRSS, VmSize, VmHWM, RssAnon, RssFile, VmSwap em MB; Threads."""
    d = _kv_file(f"/proc/{pid}/status")
    out = {}
    for k in ("VmRSS", "VmSize", "VmHWM", "VmPeak", "RssAnon", "RssFile", "RssShmem", "VmSwap"):
        if k in d:
            out[k] = int(d[k].split()[0]) / 1024.0
    if "Threads" in d:
        out["Threads"] = int(d["Threads"])
    return out


def meminfo():
    d = _kv_file("/proc/meminfo")
    out = {}
    for k in ("MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached", "SwapTotal",
              "SwapFree", "SwapCached", "Dirty", "Active(file)", "Inactive(file)"):
        if k in d:
            out[k] = int(d[k].split()[0]) / 1024.0
    return out


def proc_io(pid="self"):
    d = _kv_file(f"/proc/{pid}/io")
    return {k: int(v) for k, v in d.items()}


def rusage():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return {"minflt": r.ru_minflt, "majflt": r.ru_majflt, "utime": r.ru_utime,
            "stime": r.ru_stime, "nvcsw": r.ru_nvcsw, "nivcsw": r.ru_nivcsw,
            "maxrss_mb": r.ru_maxrss / 1024.0}


def delta(a, b):
    return {k: b[k] - a[k] for k in b if k in a and isinstance(b[k], (int, float))}


def resumo(valores):
    if not valores:
        return {"n": 0, "media": 0.0, "mediana": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    v = sorted(valores)
    return {"n": len(v), "media": statistics.fmean(v), "mediana": statistics.median(v),
            "p95": percentil(v, 95), "min": v[0], "max": v[-1]}


def percentil(v_ordenado, p):
    if not v_ordenado:
        return 0.0
    k = (len(v_ordenado) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(v_ordenado) - 1)
    return v_ordenado[lo] + (v_ordenado[hi] - v_ordenado[lo]) * (k - lo)


def residencia_cache(path):
    """Fracao das paginas de um arquivo presentes no cache de paginas (mincore)."""
    tam = os.path.getsize(path)
    if tam == 0:
        return 0.0, 0, 0
    pg = mmap.PAGESIZE
    npag = (tam + pg - 1) // pg
    lc = libc()
    lc.mmap.restype = ctypes.c_void_p
    lc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int,
                        ctypes.c_int, ctypes.c_long]
    lc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    lc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p]
    fd = os.open(path, os.O_RDONLY)
    try:
        addr = lc.mmap(None, tam, 1, 1, fd, 0)  # PROT_READ, MAP_SHARED
        if addr in (None, ctypes.c_void_p(-1).value):
            return -1.0, 0, npag
        vec = ctypes.create_string_buffer(npag)
        lc.mincore(ctypes.c_void_p(addr), tam, vec)
        residentes = sum(1 for b in vec.raw if b & 1)
        lc.munmap(ctypes.c_void_p(addr), tam)
        return residentes / npag, residentes, npag
    finally:
        os.close(fd)


def descartar_cache_arquivo(path):
    """Remove as paginas limpas do arquivo do cache (POSIX_FADV_DONTNEED)."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)


def descartar_cache_global():
    """drop_caches exige root; retorna False se nao for possivel."""
    try:
        os.sync()
        with open("/proc/sys/vm/drop_caches", "w") as f:
            f.write("3\n")
        return True
    except OSError:
        return False


class Amostrador(threading.Thread):
    """Amostra periodicamente fila, trabalhadores ocupados e memoria."""

    def __init__(self, intervalo, fn_fila=None, fn_ocupados=None):
        super().__init__(name="amostrador", daemon=True)
        self.intervalo = intervalo
        self.fn_fila = fn_fila
        self.fn_ocupados = fn_ocupados
        self.linhas = []
        self._parar = threading.Event()
        self.t0 = time.perf_counter()

    def run(self):
        nomear_thread("amostrador")
        while not self._parar.is_set():
            self.amostrar()
            self._parar.wait(self.intervalo)
        self.amostrar()

    def amostrar(self):
        st = status()
        ru = rusage()
        mi = meminfo()
        self.linhas.append({
            "t": round(time.perf_counter() - self.t0, 4),
            "fila": self.fn_fila() if self.fn_fila else 0,
            "ocupados": self.fn_ocupados() if self.fn_ocupados else 0,
            "rss_mb": round(st.get("VmRSS", 0), 2),
            "vsz_mb": round(st.get("VmSize", 0), 2),
            "rss_anon_mb": round(st.get("RssAnon", 0), 2),
            "rss_file_mb": round(st.get("RssFile", 0), 2),
            "swap_mb": round(st.get("VmSwap", 0), 2),
            "threads": st.get("Threads", 0),
            "minflt": ru["minflt"], "majflt": ru["majflt"],
            "mem_available_mb": round(mi.get("MemAvailable", 0), 1),
            "cached_mb": round(mi.get("Cached", 0), 1),
        })

    def parar(self):
        self._parar.set()
        self.join(timeout=2)
