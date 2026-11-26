#!/usr/bin/env bash
# Lanza la prueba de carga (Locust) contra el cluster = el "pico" de la demo.
# Abre la interfaz web en http://localhost:8089 (ahí: Users=300, Ramp up=30, Start).
# Dejá esta terminal abierta mientras dura el pico; Ctrl+C para cortar la carga.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/load"

if [ ! -d .venv ]; then
  echo ">> Primera vez: creando el entorno de Locust…"
  python -m venv .venv
  .venv/Scripts/python.exe -m pip install --quiet -r requirements.txt
fi

echo ""
echo ">> Locust arrancando. Abrí:  http://localhost:8089"
echo "   Poné  Number of users = 300,  Ramp up = 30,  y Start."
echo "   Vas a ver el RPS trepar (0 fallos). Ctrl+C acá para cortar la carga."
echo ""
.venv/Scripts/python.exe -m locust -f locustfile.py --host http://localhost:8088
