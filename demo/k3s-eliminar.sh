#!/usr/bin/env bash
# Borra el cluster k3s por completo (libera todo el espacio).
# Volver a crearlo desde cero con: bash demo/k3s-levantar.sh
set -euo pipefail
export PATH="$HOME/bin:$PATH"
k3d cluster delete pfi
echo "✅ Cluster 'pfi' eliminado. Recrear: bash demo/k3s-levantar.sh"
