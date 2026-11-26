#!/usr/bin/env bash
# Muestra el estado del cluster + un chequeo rápido de la app. Correr antes de grabar.
# Solo lectura: no modifica nada.
set -uo pipefail
export PATH="$HOME/bin:$PATH"
B=http://localhost:8088

port=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null | sed -E 's#.*:([0-9]+)$#\1#')
kubectl config set-cluster k3d-pfi --server="https://127.0.0.1:${port}" >/dev/null 2>&1 || true

echo "=== PODS ==="
kubectl -n pfi get pods --no-headers --request-timeout=12s 2>&1 | awk '{print "  "$2" "$3"  "$1}'
echo "=== HPA (réplicas; sin carga debería ser 1) ==="
kubectl -n pfi get hpa --request-timeout=12s 2>&1
echo "=== APP (por el gateway :8088) ==="
echo "  front:       $(curl -s -o /dev/null -w '%{http_code}' --max-time 8 $B/ 2>/dev/null)"
n=$(curl -s --max-time 8 $B/api/catalogo/productos 2>/dev/null | python -c 'import sys,json;print(len(json.load(sys.stdin)))' 2>/dev/null)
echo "  catalogo:    ${n:-ERROR} productos"
echo "  debug.html:  $(curl -s -o /dev/null -w '%{http_code}' --max-time 8 $B/debug.html 2>/dev/null)"
echo ""
echo "Si algún pod no está 'Running 1/1', esperá unos segundos y reintentá."
echo "Si kubectl da timeout: bash demo/k3s-levantar.sh (re-fija el acceso)."
