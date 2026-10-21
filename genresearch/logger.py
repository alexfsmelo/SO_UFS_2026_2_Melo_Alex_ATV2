"""Registro de eventos em JSON Lines com escrita concorrente protegida.

modo="lock":   cada linha e montada inteira e gravada em UM write() sob mutex.
modo="unsafe": a linha e gravada em fragmentos de 16 bytes, sem exclusao mutua,
               cedendo a CPU entre fragmentos (falha controlada: log intercalado).
"""
import json
import os
import threading
import time


class EventLogger:
    def __init__(self, caminho, modo="lock"):
        self.caminho = caminho
        self.modo = modo
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
        self.fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_APPEND, 0o644)
        self.lock = threading.Lock()
        self.contagem = {}
        self.fechado = False

    def log(self, evento, **campos):
        reg = {"ts": round(time.time(), 6), "thread": threading.current_thread().name,
               "evento": evento}
        reg.update(campos)
        dados = (json.dumps(reg, ensure_ascii=False) + "\n").encode("utf-8")
        if self.modo == "lock":
            with self.lock:
                os.write(self.fd, dados)
                self.contagem[evento] = self.contagem.get(evento, 0) + 1
        else:
            for i in range(0, len(dados), 16):
                os.write(self.fd, dados[i:i + 16])
                time.sleep(0)
            self.contagem[evento] = self.contagem.get(evento, 0) + 1

    def fechar(self):
        if not self.fechado:
            os.close(self.fd)
            self.fechado = True


def validar_log(caminho):
    """Conta linhas validas e corrompidas (JSON invalido) de um log JSONL."""
    total = invalidas = 0
    with open(caminho, "rb") as f:
        for linha in f:
            total += 1
            try:
                json.loads(linha)
            except ValueError:
                invalidas += 1
    return {"linhas": total, "invalidas": invalidas, "validas": total - invalidas}
