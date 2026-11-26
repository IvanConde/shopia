#!/usr/bin/env bash
# Pausa el cluster k3s (libera CPU/RAM, CONSERVA los datos).
# Reanudar luego con: bash demo/k3s-levantar.sh
set -euo pipefail
export PATH="$HOME/bin:$PATH"
k3d cluster stop pfi
echo "✅ Cluster 'pfi' detenido (datos conservados). Reanudar: bash demo/k3s-levantar.sh"
