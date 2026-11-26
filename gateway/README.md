# gateway/ — API Gateway

**Traefik** como único punto de entrada externo (entrypoint `web`, puerto 80).
Enruta por prefijo de path hacia cada microservicio y valida el **JWT en el borde**
mediante el middleware **ForwardAuth**, que delega la validación de la firma en el
servicio `auth`. Es el mismo gateway que en k3s (ahí actúa como Ingress).

## Configuración
- `traefik.yml` — configuración **estática**: entrypoint `web:80`, dashboard (dev)
  y el **file provider** (no se usa el socket de Docker).
- `dynamic.yml` — configuración **dinámica**: routers, middlewares y services,
  apuntando a cada servicio por su nombre de red interno.

## Rutas
| Path externo | Servicio | Auth |
|---|---|---|
| `/api/catalogo/*` | catalogo:8000 | público (navegación/búsqueda sin login) |
| `/api/auth/*` | auth:8000 | público (login) |
| `/api/pedidos/*` | pedidos:8000 | **JWT requerido** |
| `/api/pagos/*` | pagos:8000 | **JWT requerido** |

El middleware `jwt-auth` (ForwardAuth → `http://auth:8000/verify`) valida el token
antes de enrutar y propaga `X-User-Id` / `X-User-Email` al servicio de destino.
El dashboard de Traefik (solo dev) queda en `http://localhost:8080`.

## Prueba rápida
```bash
GW=http://localhost
# Login -> token
TOKEN=$(curl -s -X POST $GW/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"juan@shopia.demo","password":"demo"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# Público (sin token)
curl $GW/api/catalogo/productos
# Protegido (con token)
curl -H "Authorization: Bearer $TOKEN" "$GW/api/pedidos?usuario_id=11111111-1111-1111-1111-111111111111"
```
Credenciales demo: `juan@shopia.demo` / `demo`.
