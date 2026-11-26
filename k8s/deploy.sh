#!/usr/bin/env bash
# Despliegue del prototipo en k3s (vía k3d) para D3. Idempotente: se puede correr
# varias veces. No imprime la clave de Gemini. Ejecutar desde Git Bash con Docker
# Desktop corriendo y las imágenes pfi-* ya construidas (docker compose build).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER="pfi"
HOST_PORT="8088"         # http://localhost:8088 -> ingress del cluster (:80)
ENVFILE="$HERE/../infra/.env"

IMAGES=(pfi-catalogo pfi-pedidos pfi-pagos pfi-auth pfi-usuarios pfi-stock \
        pfi-mcp pfi-agente pfi-anomalias pfi-notificaciones pfi-front)

command -v k3d >/dev/null 2>&1 || { echo "ERROR: k3d no está instalado (ver README.md)"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "ERROR: kubectl no está instalado"; exit 1; }

# 1) Cluster (si no existe). Mapea el puerto del ingress al host.
if ! k3d cluster list 2>/dev/null | awk '{print $1}' | grep -qx "$CLUSTER"; then
  echo ">> Creando cluster k3d '$CLUSTER' (ingress en localhost:$HOST_PORT)…"
  k3d cluster create "$CLUSTER" --servers 1 --port "${HOST_PORT}:80@loadbalancer" --wait
else
  echo ">> Cluster '$CLUSTER' ya existe."
fi

# 2) Namespace + ConfigMaps.
kubectl apply -f "$HERE/00-namespace-config.yaml"

# 3) Secret desde el .env (no se imprime la clave).
GEMINI="$(grep -E '^GEMINI_API_KEY=' "$ENVFILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d '\r' || true)"
[ -n "$GEMINI" ] || echo "AVISO: no se encontró GEMINI_API_KEY en $ENVFILE → el agente/notif. usarán el respaldo."
kubectl -n pfi create secret generic pfi-secrets \
  --from-literal=JWT_SECRET="dev-secret-cambiar" \
  --from-literal=GEMINI_API_KEY="${GEMINI:-}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 4) Importar las imágenes locales al cluster (no hay registry).
echo ">> Importando imágenes al cluster (puede tardar)…"
k3d image import "${IMAGES[@]/%/:latest}" -c "$CLUSTER"

# 5) Infra y, cuando Postgres esté listo, el resto.
kubectl apply -f "$HERE/10-infra.yaml"
echo ">> Esperando PostgreSQL…"
kubectl -n pfi rollout status deploy/postgres --timeout=180s
kubectl apply -f "$HERE/20-services-dominio.yaml"
kubectl apply -f "$HERE/30-services-ia.yaml"
kubectl apply -f "$HERE/40-front.yaml"
kubectl apply -f "$HERE/50-ingress.yaml"
kubectl apply -f "$HERE/60-hpa.yaml"

echo ">> Esperando a que los servicios estén listos…"
kubectl -n pfi rollout status deploy/catalogo --timeout=180s || true
echo
echo "Listo. Prototipo en k3s:"
echo "  Front/API:  http://localhost:${HOST_PORT}"
echo "  Estado:     kubectl -n pfi get pods,hpa"
echo "  Carga:      load/README.md  (apuntar Locust a http://localhost:${HOST_PORT})"
