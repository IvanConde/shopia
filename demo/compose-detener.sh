#!/usr/bin/env bash
# Detiene el stack compose (CONSERVA los datos). Reanudar: compose-levantar.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/infra"
docker compose stop
echo "✅ Stack compose detenido (datos conservados)."
