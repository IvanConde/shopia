#!/usr/bin/env bash
# Observa el autoescalado EN VIVO: la columna REPLICAS del HPA sube de 1 a 5 (catálogo)
# y a 4 (pedidos) cuando corre el pico, y baja sola al terminar. Ctrl+C para salir.
# Abrí esta terminal ANTES de lanzar la carga para verlo escalar.
set -uo pipefail
export PATH="$HOME/bin:$PATH"

port=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null | sed -E 's#.*:([0-9]+)$#\1#')
kubectl config set-cluster k3d-pfi --server="https://127.0.0.1:${port}" >/dev/null 2>&1 || true

echo ">> HPA en vivo (Ctrl+C para salir)."
echo "   Para ver además los pods naciendo, abrí OTRA terminal con:"
echo "     kubectl -n pfi get pods -l app=catalogo -w"
echo ""
kubectl -n pfi get hpa -w
