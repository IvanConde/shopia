#!/usr/bin/env bash
# Resetea el stack compose a CERO (borra volúmenes/datos) y lo vuelve a levantar.
# Deja: 0 pedidos, 16 productos, stock lleno. Para dev; la demo del pico va por k3s.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
docker version >/dev/null 2>&1 || { echo "ERROR: Docker Desktop no responde."; exit 1; }
cd "$ROOT/infra"
docker compose down -v
docker compose up -d
echo ""
echo "✅ Stack compose reseteado a CERO en http://localhost."
