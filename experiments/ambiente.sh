#!/usr/bin/env bash
# Parte A: registro do ambiente. Saida em results/evidence/ambiente.txt
cd "$(dirname "$0")/.." || exit 1
OUT=results/evidence/ambiente.txt
mkdir -p results/evidence
{
  echo "### data da coleta"; date -Iseconds
  echo; echo "### commit do repositorio"; git rev-parse HEAD 2>/dev/null || echo "(sem git nesta copia)"
  echo; echo "### uname -a"; uname -a
  echo; echo "### /etc/os-release"; cat /etc/os-release
  echo; echo "### virtualizacao"; (systemd-detect-virt 2>/dev/null || true); grep -m1 -i hypervisor /proc/cpuinfo >/dev/null && echo "flag hypervisor presente em /proc/cpuinfo"
  echo; echo "### lscpu"; lscpu
  echo; echo "### free -h"; free -h
  echo; echo "### swapon --show"; swapon --show; echo "(vazio = sem swap ativo)"
  echo; echo "### /proc/meminfo"; cat /proc/meminfo
  echo; echo "### vm.swappiness / overcommit / dirty"; for k in swappiness overcommit_memory dirty_ratio dirty_background_ratio; do echo "$k=$(cat /proc/sys/vm/$k)"; done
  echo; echo "### page size"; getconf PAGESIZE
  echo; echo "### lsblk"; lsblk -o NAME,SIZE,TYPE,ROTA,MOUNTPOINT 2>/dev/null || lsblk
  echo; echo "### df -hT ."; df -hT .
  echo; echo "### mount (raiz)"; mount | grep " / "
  echo; echo "### cgroups"; cat /proc/self/cgroup
  echo; echo "### GPU"; (nvidia-smi 2>/dev/null || echo "sem GPU NVIDIA / nvidia-smi ausente")
  echo; echo "### python e bibliotecas"; python3 --version; python3 -c "import numpy, sqlite3, sys; print('numpy', numpy.__version__); print('sqlite', sqlite3.sqlite_version)"; python3 -c "import matplotlib; print('matplotlib', matplotlib.__version__)" 2>/dev/null
  echo; echo "### ferramentas"; for t in strace vmstat iostat pidstat ps; do printf "%s: " $t; command -v $t || echo ausente; done; strace -V 2>/dev/null | head -1
  echo; echo "### ollama"; (ollama --version 2>/dev/null || echo "ollama nao instalado neste ambiente; geracao simulada")
  echo; echo "### vmstat 1 5"; vmstat 1 5
  echo; echo "### iostat -xz 1 2"; (iostat -xz 1 2 2>/dev/null || echo "iostat ausente")
} > "$OUT" 2>&1
echo "ambiente gravado em $OUT"
