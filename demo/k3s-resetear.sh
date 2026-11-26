#!/usr/bin/env bash
# Resetea la demo a CERO: borra el cluster y lo recrea limpio.
# Deja: 0 pedidos, 0 alertas, 16 productos, stock lleno. Ideal antes de grabar.
# Nota: usa las imágenes ya construidas; si CAMBIASTE código, primero rebuildeá
# (cd infra && docker compose build). Correr desde Git Bash. Tarda ~3-4 min.
set -euo pipefail
export PATH="$HOME/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v k3d >/dev/null || { echo "ERROR: k3d no está en PATH."; exit 1; }
docker version >/dev/null 2>&1 || { echo "ERROR: Docker Desktop no responde."; exit 1; }

echo ">> Borrando el cluster 'pfi'…"
k3d cluster delete pfi 2>/dev/null || true
echo ">> Recreando limpio y desplegando…"
k3d cluster create pfi --servers 1 --port "8088:80@loadbalancer" --wait
port=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' | sed -E 's#.*:([0-9]+)$#\1#')
kubectl config set-cluster k3d-pfi --server="https://127.0.0.1:${port}" >/dev/null 2>&1
bash "$ROOT/k8s/deploy.sh"
kubectl -n pfi wait --for=condition=ready pod --all --timeout=180s >/dev/null 2>&1 || true

# La siembra de stock corre al arrancar el servicio consultando al catálogo; si
# el catálogo todavía no había sembrado sus productos, el stock queda vacío (la
# web mostraría "Stock s/d"). Esperamos a que el catálogo tenga sus 16 productos
# y reiniciamos stock para que vuelva a sembrar contra un catálogo ya poblado.
echo ">> Asegurando la siembra de stock…"
for _ in $(seq 1 30); do
  n=$(curl -s http://localhost:8088/api/catalogo/productos 2>/dev/null | grep -o '"id"' | wc -l)
  [ "${n:-0}" -ge 16 ] && break
  sleep 2
done
kubectl -n pfi rollout restart deploy/stock >/dev/null 2>&1 || true
kubectl -n pfi rollout status deploy/stock --timeout=90s >/dev/null 2>&1 || true
echo ""
echo "✅ Cluster reseteado a CERO. Front en http://localhost:8088 (0 pedidos, 16 productos con stock)."
