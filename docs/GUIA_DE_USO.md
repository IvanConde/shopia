# Guía de uso — ShopIA

Cómo levantar el prototipo, **por dónde se accede a cada cosa** y **cómo probar/observar**
cada componente. Todo corre local en contenedores Docker; sin costos ni cuentas externas.

> Estado: componentes implementados y verificados (infra, Catálogo, Pedidos, Pagos, Gateway
> con JWT, bus de eventos y **agente conversacional MCP**), más un **frontend web de
> demo** (chat con el agente + panel de traza ReAct) servido detrás del gateway. Otras
> UIs navegables para inspección: las Swagger, el dashboard de Traefik y la consola de
> RabbitMQ.

---

## 1. Requisitos y arranque

- **Docker Desktop** en ejecución (Engine 24+, Compose v2).

```bash
cd infra
docker compose up -d       # levanta los 11 contenedores
docker compose ps          # ver estado (todos deben quedar "healthy")
docker compose logs -f     # ver logs en vivo (Ctrl-C para salir)
docker compose down        # bajar (conserva los datos)
docker compose down -v     # bajar y borrar volúmenes (resetea la BD)
```

La primera vez, Docker construye las imágenes de los servicios (tarda unos minutos).

**Credenciales de demostración** (usuario comprador, coherente con los mockups):
`juan@shopia.demo` / `demo`.

---

## 2. Mapa de accesos (URLs, puertos, credenciales)

Todo se sirve en `localhost` (IP `127.0.0.1`). No hay nada expuesto fuera de la máquina.

| Qué | URL / puerto | Credenciales | Para qué sirve |
|---|---|---|---|
| **Frontend de demo (chat)** | `http://localhost` (:80) | auto-login (usuario demo) | **La pantalla principal:** chat con el agente + panel de traza ReAct. |
| **API Gateway (Traefik)** | `http://localhost` (:80) | — (JWT en rutas protegidas) | **Único punto de entrada real.** Enruta al front y a todos los servicios. |
| **Dashboard de Traefik** | `http://localhost:8080` | — | Ver routers, services y middlewares (routing + JWT). *Solo dev.* |
| **Consola de RabbitMQ** | `http://localhost:15672` | `pfi` / `pfi` | Ver exchanges, colas, mensajes y tasas (el bus de eventos). |
| **Catálogo — API docs** | `http://localhost:8001/docs` | — | Swagger interactivo del servicio Catálogo. *Puerto dev.* |
| **Pedidos — API docs** | `http://localhost:8002/docs` | — | Swagger del servicio Pedidos. *Puerto dev.* |
| **Pagos — API docs** | `http://localhost:8003/docs` | — | Swagger del servicio Pagos. *Puerto dev.* |
| **Auth — API docs** | `http://localhost:8004/docs` | — | Swagger del servicio de autenticación. *Puerto dev.* |
| **Agente — API docs** | `http://localhost:8005/docs` | — | Swagger del agente conversacional (`/chat`). *Puerto dev.* |
| **Frontend (directo)** | `http://localhost:8006` | auto-login | El front servido directo por su contenedor. El acceso real de la demo es por el gateway (`http://localhost`). *Puerto dev.* |
| **Servidor MCP** | `http://localhost:8010/mcp` | — | Endpoint MCP (streamable-http) que consume el agente. *Interno; puerto dev.* |
| **PostgreSQL** | `localhost:5432` (db `pfi`) | `pfi` / `pfi` | Base de datos (un esquema por servicio). |
| **Redis** | `localhost:6379` | — | Caché (se usará en el agente/notificaciones). |

> **Nota de arquitectura:** en el diseño de producción (k3s) el **único** puerto expuesto
> es el del gateway. Los puertos directos `8001`–`8006`, `8010`, `5432`, `6379`, `15672` y
> `8080` están publicados **solo en desarrollo** (atados a `127.0.0.1`) para inspeccionar. No son parte de la superficie pública.

### ¿Hay un frontend web?
Sí. Hay un **frontend web mínimo** (React + TypeScript + Vite) pensado para la
**interfaz principal**: una pantalla de **chat con el agente** y, al costado, un
**panel de traza** que muestra el razonamiento ReAct (pensamiento → acción → observación)
paso a paso. Se accede en **`http://localhost`** (se sirve detrás del gateway, mismo
origen que la API). Detalle de uso en la [sección 4c](#4c-frontend-de-demo-chat--traza).
El frontend hace **auto-login** con el usuario demo al cargar, así que en la defensa solo
hay que escribir (o clickear un botón) en el chat. Para inspeccionar componentes internos
siguen estando las **API docs (Swagger)**, el **dashboard de Traefik** y la **consola de
RabbitMQ**.

---

## 3. Rutas del gateway (cómo se usa la API)

Todo pasa por `http://localhost`. Prefijo `/api/<servicio>`.

| Método y ruta | Servicio | ¿Requiere login? |
|---|---|---|
| `GET /api/catalogo/productos?q=<texto>` | Catálogo — buscar | No (público) |
| `GET /api/catalogo/productos/{id}` | Catálogo — detalle | No (público) |
| `GET /api/catalogo/categorias` | Catálogo — categorías | No (público) |
| `POST /api/auth/login` | Auth — obtener JWT | No (público) |
| `POST /api/pedidos` | Pedidos — checkout | **Sí (JWT)** |
| `GET /api/pedidos/{id}` | Pedidos — seguimiento | **Sí (JWT)** |
| `GET /api/pedidos?usuario_id=<id>` | Pedidos — historial | **Sí (JWT)** |
| `GET /api/pagos` | Pagos — pagos simulados procesados | **Sí (JWT)** |
| `POST /api/agente/chat` | Agente conversacional | **Sí (JWT)** |

Regla de diseño: **navegar y buscar no requieren sesión**; **comprar y consultar datos
propios sí**. El JWT lo valida Traefik en el borde (delega en el servicio `auth`).

---

## 4. Recorrido de prueba end-to-end (demo)

Copiar y pegar en una terminal (bash). Muestra el flujo completo del prototipo.

```bash
GW=http://localhost
UID=11111111-1111-1111-1111-111111111111

# 1) Buscar productos (público, sin token)
curl -s "$GW/api/catalogo/productos?q=aura" | python -m json.tool

# 2) Iniciar sesión y guardar el token
TOKEN=$(curl -s -X POST "$GW/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"juan@shopia.demo","password":"demo"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 3) Intentar comprar SIN token -> 401 (bloqueado en el gateway)
curl -s -o /dev/null -w "sin token -> HTTP %{http_code}\n" \
  "$GW/api/pedidos?usuario_id=$UID"

# 4) Crear un pedido CON token -> 201 (Pedidos publica el evento pedidos.creados)
PROD=$(curl -s "$GW/api/catalogo/productos?q=Aura%20Pro" \
  | python -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
curl -s -X POST "$GW/api/pedidos" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"usuario_id\":\"$UID\",\"items\":[{\"producto_id\":\"$PROD\",\"cantidad\":2}]}" \
  | python -m json.tool

# 5) Ver el pago simulado que Pagos generó al consumir el evento (85% aprob / 15% rech)
curl -s -H "Authorization: Bearer $TOKEN" "$GW/api/pagos" | python -m json.tool
```

**Qué observar mientras tanto:**
- En la **consola de RabbitMQ** (`http://localhost:15672` → *Queues and Streams*): la cola
  `pagos.pedidos_creados` con su consumidor y las tasas de mensajes subiendo al crear pedidos.
- En los **logs**: `docker logs pfi-pedidos` muestra `Evento publicado: pedidos.creados`;
  `docker logs pfi-pagos` muestra `Pago simulado pedido=... -> completado/rechazado`.
- En el **dashboard de Traefik** (`http://localhost:8080` → HTTP): los routers y el
  middleware `jwt-auth` que protege `/api/pedidos` y `/api/pagos`.

---

## 4b. Probar el agente conversacional

El agente responde preguntas en lenguaje natural razonando con el patrón **ReAct**
(pensar → invocar herramienta → observar → responder). Las herramientas se las
provee un **servidor MCP** que hace de fachada a Catálogo y Pedidos, así que las
respuestas salen de **datos reales**.

```bash
AG=http://localhost:8005     # puerto dev directo (sin gateway)

# ¿Qué backend está activo? (fallback = reglas; gemini = modelo real)
curl -s $AG/health

# Estado de un pedido (poné un id real, p. ej. el que devuelve POST /pedidos)
curl -s -X POST $AG/chat -H "Content-Type: application/json" \
  -d '{"mensaje":"como va mi pedido <UUID-de-pedido> ?"}'

# Buscar productos
curl -s -X POST $AG/chat -H "Content-Type: application/json" \
  -d '{"mensaje":"quiero auriculares aura"}'

# Historial de un usuario
curl -s -X POST $AG/chat -H "Content-Type: application/json" \
  -d '{"mensaje":"mostrame mi historial del usuario 11111111-1111-1111-1111-111111111111"}'
```

La respuesta incluye la **traza** (`pensamiento`, `accion`, `observacion`) que
alimenta el panel de traza del chat en los mockups. Por el **gateway**, la ruta
`POST /api/agente/chat` exige JWT (como toda ruta que toca datos del usuario).

### Backend del modelo: `fallback` vs `gemini`
- **`fallback`** (por defecto, sin credenciales): un planificador determinista por
  reglas elige la herramienta MCP y redacta la respuesta. Sirve para demostrar todo
  el flujo MCP + ReAct **sin costo ni claves**.
- **`gemini`** (opcional, free tier): un modelo real de Google razona sobre las
  mismas herramientas. Para activarlo:
  1. Generar una API key en <https://aistudio.google.com/apikey> (gratis).
  2. En `infra/.env` (el archivo que lee docker compose): `GEMINI_API_KEY=<tu-clave>`
     (opcional `MODELO_GEMINI=gemini-flash-lite-latest`, más cuota y menor latencia).
  3. `cd infra && docker compose up -d agente` y comprobar
     `curl localhost:8005/health` → `"backend":"gemini"`.

  La clave vive **solo** en `infra/.env` (git-ignorado), nunca en el código ni en el
  compose. El free tier tiene **cuota diaria acotada por modelo**; si se agota, el agente
  degrada solo al respaldo (`backend: fallback`) sin cortar el servicio.

---

## 4c. Frontend de demo (chat + traza)

La pantalla pensada para la **defensa oral**. Se abre en **`http://localhost`** (por el
gateway; no hace falta puerto). Al cargar:

1. Hace **auto-login** con el usuario demo (`juan@shopia.demo`) — el presentador no toca
   la consola.
2. **Resuelve un pedido real** del usuario (usa el más reciente de su historial o crea
   uno) para que el botón *"¿En qué anda mi pedido?"* siempre tenga contra qué resolver.
3. Queda lista para chatear. Hay **botones de consulta sugerida** (pedido, búsqueda,
   historial) o se puede escribir libremente.

Con cada respuesta, el **panel de traza** (derecha) revela paso a paso el razonamiento
del agente: *pensamiento → acción (herramienta MCP) → observación (dato real devuelto)*.
Un **chip de estado** en la cabecera indica el backend activo (`Gemini` o `Motor local`),
así queda a la vista si el modelo real está respondiendo o si se degradó al respaldo.

### Modo auto-demo (kiosco)
La pantalla acepta un parámetro `?auto=` que lanza una consulta sola al cargar, útil para
proyectar sin tocar nada:

- `http://localhost/?auto=pedido` — consulta el estado del pedido demo.
- `http://localhost/?auto=buscar` — busca auriculares.
- `http://localhost/?auto=historial` — muestra el historial del usuario demo.

> **Nota de robustez:** *navegar* el catálogo es público, pero el **chat pasa por JWT**
> (como toda ruta que toca datos del usuario). El front obtiene y adjunta el token solo;
> si el free tier de Gemini agota su cuota diaria, el agente degrada al respaldo
> determinista y el chip pasa a *"Motor local"*, sin cortar la demo.

---

## 5. Cómo observar cada componente

- **Gateway / routing / JWT:** dashboard de Traefik (`:8080`), pestaña *HTTP* → *Routers*,
  *Services*, *Middlewares*.
- **Bus de eventos:** consola de RabbitMQ (`:15672`). *Exchanges* → `pfi.events` (topic,
  durable). *Queues* → `pagos.pedidos_creados` (durable, 1 consumidor).
- **Base de datos:** la forma más simple (una consulta por vez, funciona igual en cmd y
  PowerShell) es pasar el SQL con `-c`:
  ```
  docker exec pfi-postgres psql -U pfi -d pfi -c "\dn"
  docker exec pfi-postgres psql -U pfi -d pfi -c "SELECT * FROM catalogo.producto;"
  docker exec pfi-postgres psql -U pfi -d pfi -c "SELECT id, estado, total FROM pedidos.pedido ORDER BY creado_en DESC;"
  ```
  Para una **sesión interactiva** (prompt `pfi=#`) hace falta `-it`, y como la base usa un
  **esquema por servicio**, hay que nombrar el esquema al listar tablas (`\dt` a secas mira
  `public`, que está vacío):
  ```
  docker exec -it pfi-postgres psql -U pfi -d pfi
  ```
  ```
  \dn              -- esquemas (usuarios, catalogo, stock, pedidos, pagos, anomalias, notificaciones)
  \dt catalogo.*   -- tablas de un esquema (NO "\dt" solo)
  SELECT * FROM catalogo.producto;
  \q               -- salir
  ```
  > **Ojo:** sin `-it`, `docker exec ... psql ...` a secas abre la sesión interactiva sin
  > terminal, lee fin-de-entrada y **sale sin mostrar nada** (parece que "no hace nada").
  > Hoy solo `catalogo` y `pedidos` tienen tablas con datos; el resto de esquemas están
  > creados pero vacíos (servicios de diseño).
- **Servicios (endpoints):** Swagger de cada uno (`:8001`–`:8005` `/docs`), donde se pueden
  ejecutar las llamadas desde el navegador.
- **Agente / MCP:** `docker logs pfi-agente` muestra las herramientas MCP descubiertas al
  arrancar y el backend activo (`fallback`/`gemini`); `docker logs pfi-mcp` muestra las
  invocaciones de herramientas. La respuesta de `/chat` trae la traza de razonamiento.
- **Estado general:** `cd infra && docker compose ps` (todos `healthy`).

---

## 6. Componentes en ejecución (resumen)

| Contenedor | Imagen | Rol |
|---|---|---|
| `pfi-gateway` | traefik:v3.1 | API Gateway (routing + JWT) |
| `pfi-auth` | (build) | Emite y valida JWT |
| `pfi-catalogo` | (build) | Catálogo: búsqueda y detalle |
| `pfi-pedidos` | (build) | Pedidos: checkout, seguimiento, historial |
| `pfi-pagos` | (build) | Pago simulado (consume `pedidos.creados`) |
| `pfi-mcp` | (build) | Servidor MCP de dominio (herramientas del agente) |
| `pfi-agente` | (build) | Agente conversacional ReAct (`/chat`) |
| `pfi-front` | (build) | Frontend de demo (chat + panel de traza); nginx sirve el estático |
| `pfi-postgres` | postgres:16-alpine | Base de datos (esquema por servicio) |
| `pfi-redis` | redis:7-alpine | Caché |
| `pfi-rabbitmq` | rabbitmq:3.13-management | Bus de eventos (AMQP) |

