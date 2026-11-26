# Despliegue en Kubernetes (k3s) — D3

Manifests para correr el prototipo en **k3s** y demostrar el **autoescalado (HPA)**
bajo carga (Locust). Es el paso que demuestra la escalabilidad horizontal del sistema.

**Host:** k3s local vía **k3d** (k3s dentro de Docker). Es k3s real, aprovecha Docker Desktop y las
imágenes `pfi-*` ya construidas, trae Traefik (ingress) y metrics-server (HPA).

## Qué hay acá

| Archivo | Contenido |
|---|---|
| `00-namespace-config.yaml` | Namespace `pfi` + ConfigMap común + init SQL de los 7 esquemas |
| `01-secrets.example.yaml` | Plantilla del Secret (la clave real la pone `deploy.sh` desde `.env`) |
| `10-infra.yaml` | PostgreSQL (con PVC), Redis, RabbitMQ |
| `20-services-dominio.yaml` | Catálogo, Pedidos, Pagos, Auth, Usuarios, Stock |
| `30-services-ia.yaml` | MCP, Agente, Anomalías, Notificaciones |
| `40-front.yaml` | Frontend de demo |
| `50-ingress.yaml` | El gateway como Traefik: rate limiting + JWT (ForwardAuth) + routing |
| `60-hpa.yaml` | HorizontalPodAutoscaler de `catalogo` y `pedidos` |
| `deploy.sh` | Crea cluster, Secret, importa imágenes y aplica todo |

## Requisitos

- Docker Desktop corriendo y las imágenes construidas: `cd infra && docker compose build`.
- `kubectl` (ya instalado).
- `k3d`. Si no está, bajar el binario (sin admin) a una carpeta del PATH, p. ej.:
  ```bash
  mkdir -p ~/bin
  curl -L -o ~/bin/k3d.exe \
    https://github.com/k3d-io/k3d/releases/download/v5.7.5/k3d-windows-amd64.exe
  k3d version
  ```
  (o `choco install k3d` con permisos de administrador).

## Desplegar

```bash
cd k8s
./deploy.sh
```

Deja el prototipo en **http://localhost:8088** (front + API, igual que el `:80` del
compose). Estado: `kubectl -n pfi get pods,hpa`.

## Operar el cluster (arrancar / parar / borrar)

```bash
export PATH="$HOME/bin:$PATH"     # si k3d está en ~/bin
k3d cluster stop pfi              # pausa (libera RAM/CPU, conserva todo)
k3d cluster start pfi             # reanuda
k3d cluster delete pfi            # borra el cluster entero
kubectl -n pfi get pods,hpa       # estado
```

> ⚠️ **Windows/k3d + kubectl:** el kubeconfig que genera k3d apunta a
> `host.docker.internal`, que en esta notebook no responde. Si `kubectl` da
> timeout, apuntarlo a loopback (el puerto puede cambiar en cada `start`):
> ```bash
> PORT=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' | sed -E 's#.*:([0-9]+)$#\1#')
> kubectl config set-cluster k3d-pfi --server="https://127.0.0.1:${PORT}"
> ```

## Demostrar el autoescalado (HPA)

1. Ver el HPA y las réplicas en vivo (una terminal):
   ```bash
   kubectl -n pfi get hpa -w
   # en otra: kubectl -n pfi get pods -l app=catalogo -w
   ```
2. Generar carga con Locust contra el ingress (ver `load/`):
   ```bash
   cd load
   locust -f locustfile.py --host http://localhost:8088 --headless -u 300 -r 30 -t 3m
   ```
3. Al subir el uso de CPU de `catalogo` por encima del umbral (50%), el HPA
   **agrega réplicas** (hasta 5); al terminar la carga, las retira. Esa transición
   1→N→1 es la evidencia de elasticidad para V3.

> **Rate limiting vs. carga:** el ingress limita a ~300 RPS. Para una
> prueba de *saturación* pura, subir `average/burst` en el Middleware `ratelimit`
> (`50-ingress.yaml`) y reaplicar. Para ver el HPA alcanza con la carga por defecto.

## Limpiar

```bash
k3d cluster delete pfi
```

> El `docker compose` sigue siendo el entorno de demo/desarrollo; k3s es para la
> prueba de escalabilidad. Ambos usan las mismas imágenes.
