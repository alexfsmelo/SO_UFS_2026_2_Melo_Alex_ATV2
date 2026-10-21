"""Extrai de um strace -e as chamadas sobre o descritor do arquivo de vetores
(da abertura principal ate o close). Uso: resumir_strace.py strace.txt saida.txt"""
import re
import sys

ent, sai = sys.argv[1], sys.argv[2]
linhas = open(ent, encoding="utf-8", errors="replace").read().splitlines()
aberturas = [k for k, l in enumerate(linhas) if "vectors.f32" in l and "openat(" in l and "= " in l]
out = []
if aberturas:
    # a sonda abre o arquivo 3 vezes: mincore antes, leitura principal, mincore depois
    k0 = aberturas[1] if len(aberturas) >= 3 else aberturas[-1]
    fd = re.search(r"= (\d+)", linhas[k0]).group(1)
    out.append(linhas[k0])
    pad = re.compile(rf"(read|pread64|mmap|munmap|madvise|close)\((NULL, \d+, [^)]*, {fd}, |{fd}[,)])")
    n_read = 0
    bytes_read = 0
    for l in linhas[k0 + 1:]:
        if pad.search(l) or (l.split() and "mmap(" in l and f", {fd}, 0)" in l):
            if "read(" in l:
                n_read += 1
                m = re.search(r"= (\d+)$", l)
                if m:
                    bytes_read += int(m.group(1))
            out.append(re.sub(r'"[^"]{20,}"\.\.\.', '"..."', l)[:160])
            if f"close({fd})" in l:
                break
    out.append(f"--- read() sobre o fd {fd}: {n_read} chamadas, {bytes_read} bytes")
open(sai, "w").write("\n".join(out) + "\n")
print("\n".join(out))
