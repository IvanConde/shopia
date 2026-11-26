#!/usr/bin/env bash
# Levanta el stack con docker compose = entorno de DESARROLLO en http://localhost
# OJO: compose NO autoescala. Para la DEMO del pico usá k3s (k3s-levantar.sh).
# Útil para probar el front/los servicios rápido sin levantar Kubernetes.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
docker version >/dev/null 2>&1 || { echo "ERROR: Docker Desktop no responde."; exit 1; }
cd "$ROOT/infra"
docker compose up -d
echo ""
echo "✅ Stack compose arriba en http://localhost  (dev; sin autoescalado)."
