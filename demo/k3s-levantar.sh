#!/usr/bin/env bash
# Levanta (o reanuda) el cluster k3s de la demo en http://localhost:8088.
# Idempotente: si el cluster ya existe lo reanuda; si no, lo crea y despliega.
# Es el entorno de la DEMO (autoescala de verdad). Correr desde Git Bash.
set -euo pipefail
export PATH="$HOME/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v k3d >/dev/null     || { echo "ERROR: k3d no está en PATH (ver k8s/README.md)."; exit 1; }
command -v kubectl >/dev/null || { echo "ERROR: kubectl no está en PATH."; exit 1; }
docker version >/dev/null 2>&1 || { echo "ERROR: Docker Desktop no responde. Abrilo y reintentá."; exit 1; }

fix_kubeconfig() {
  local port
  port=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null | sed -E 's#.*:([0-9]+)$#\1#')
  kubectl config set-cluster k3d-pfi --server="https://127.0.0.1:${port}" >/dev/null 2>&1 || true
}

nuevo=0
if k3d cluster list 2>/dev/null | awk '{print $1}' | grep -qx pfi; then
  echo ">> El cluster 'pfi' ya existe. Reanudando…"
  k3d cluster start pfi
  fix_kubeconfig
  # Si por algún motivo no quedaron los manifests, los aplica.
  kubectl -n pfi get deploy >/dev/null 2>&1 || bash "$ROOT/k8s/deploy.sh"
else
  echo ">> Creando el cluster 'pfi' y desplegando (tarda ~2-3 min)…"
  k3d cluster create pfi --servers 1 --port "8088:80@loadbalancer" --wait
  fix_kubeconfig
  bash "$ROOT/k8s/deploy.sh"
  nuevo=1
fi

echo ">> Esperando a que los pods estén listos…"
kubectl -n pfi wait --for=condition=ready pod --all --timeout=180s >/dev/null 2>&1 || true

# En un cluster recién creado la siembra de stock puede correr antes de que el
# catálogo termine (quedaría "Stock s/d" en la web). Esperamos los 16 productos
# y reiniciamos stock para que vuelva a sembrar contra un catálogo ya poblado.
if [ "$nuevo" = "1" ]; then
  echo ">> Asegurando la siembra de stock…"
  for _ in $(seq 1 30); do
    n=$(curl -s http://localhost:8088/api/catalogo/productos 2>/dev/null | grep -o '"id"' | wc -l)
    [ "${n:-0}" -ge 16 ] && break
    sleep 2
  done
  kubectl -n pfi rollout restart deploy/stock >/dev/null 2>&1 || true
  kubectl -n pfi rollout status deploy/stock --timeout=90s >/dev/null 2>&1 || true
fi
echo ""
echo "✅ Listo. Front/API en: http://localhost:8088"
echo "   Ver estado:  bash demo/k3s-estado.sh"
