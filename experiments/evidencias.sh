#!/usr/bin/env bash
# Evidencias de processos, threads, chamadas de sistema, memoria e E/S.
cd "$(dirname "$0")/.." || exit 1
E=results/evidence
mkdir -p $E results/raw/evid

# 1. strace -c: perfil de chamadas de sistema de uma execucao completa do servidor
strace -f -c -o $E/strace_resumo_servidor.txt \
  python3 -m genresearch serve --indice index/M --saida results/raw/evid --rotulo strace_srv \
  --requisicoes 80 --trabalhadores 4 --cache-tam 32 --carga mista --quiet

# 2. strace de leitura convencional x mmap sobre o mesmo arquivo de vetores (L)
for modo in read mmap; do
  strace -f -tt -e trace=openat,read,pread64,mmap,munmap,madvise,close \
    -o $E/strace_${modo}_L.txt python3 -m genresearch.ioprobe index/L/vectors.f32 --modo $modo >/dev/null
  python3 experiments/resumir_strace.py $E/strace_${modo}_L.txt $E/strace_${modo}_L_resumo.txt >/dev/null
done
strace -c -f -o $E/strace_resumo_read_L.txt python3 -m genresearch.ioprobe index/L/vectors.f32 --modo read >/dev/null
strace -c -f -o $E/strace_resumo_mmap_L.txt python3 -m genresearch.ioprobe index/L/vectors.f32 --modo mmap >/dev/null

# 3. processo em execucao: threads, memoria, mapeamentos
python3 -m genresearch serve --indice index/L --saida results/raw/evid --rotulo proc_vivo \
  --requisicoes 400 --trabalhadores 4 --produtores 2 --chegada-ms 5 --quiet &
PID=$!
sleep 2.5
{
  echo "### ps -o pid,ppid,nlwp,stat,rss,vsz,pcpu,cmd -p $PID"; ps -o pid,ppid,nlwp,stat,rss,vsz,pcpu,cmd -p $PID
  echo; echo "### ps -L (threads)"; ps -L -o pid,lwp,stat,pcpu,comm,wchan:24 -p $PID
  echo; echo "### /proc/$PID/task/*/comm"; for t in /proc/$PID/task/*; do echo "$(basename $t) $(cat $t/comm) $(cat $t/wchan 2>/dev/null)"; done
  echo; echo "### /proc/$PID/status (memoria)"; grep -E "^(Name|State|Threads|VmPeak|VmSize|VmHWM|VmRSS|RssAnon|RssFile|RssShmem|VmSwap|voluntary|nonvoluntary)" /proc/$PID/status
  echo; echo "### /proc/$PID/maps (arquivos do indice mapeados)"; grep -E "index/" /proc/$PID/maps
  echo; echo "### /proc/$PID/smaps do vectors.f32"; awk '/vectors.f32/{f=1} f&&/^(Size|Rss|Pss|Shared_Clean|Private_Clean|Anonymous):/{print} f&&/^VmFlags/{f=0}' /proc/$PID/smaps
  echo; echo "### /proc/$PID/io"; cat /proc/$PID/io
  echo; echo "### descritores abertos"; ls -l /proc/$PID/fd | awk '{print $9,$10,$11}'
  echo; echo "### pidstat -t (1 s)"; (pidstat -t -p $PID 1 1 2>/dev/null || echo "pidstat ausente")
} > $E/processo_vivo.txt 2>&1
wait $PID

# 4. iostat e vmstat durante leitura fria do XL
sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null
(iostat -xz 1 6 > $E/iostat_leitura_fria_XL.txt 2>&1 &)
(vmstat -t 1 6 > $E/vmstat_leitura_fria_XL.txt 2>&1 &)
sleep 1
python3 -m genresearch.ioprobe index/XL_vectors.f32 --modo read > $E/ioprobe_XL_read_frio.json
sleep 5
echo "evidencias em $E"
