# ShopIA — E-commerce con microservicios y personalización por IA

Prototipo funcional de una plataforma de e-commerce construida sobre una
**arquitectura de microservicios** con **autoescalado horizontal** y tres
**módulos de inteligencia artificial**. Todo el stack corre **local y gratuito**
(contenedores Docker; el LLM usa el *free tier* de Google Gemini o un respaldo
determinista, sin costo).

## Arquitectura

- **Microservicios de dominio (FastAPI):** Catálogo, Stock, Pedidos, Usuarios y Pagos.
- **Servicio de autenticación:** emite y valida JWT.
- **Módulos de IA:**
  - **Motor de notificaciones adaptativas** — redacta avisos con un LLM + *guardrails*,
    adaptando tono y canal al perfil del cliente, con caché en Redis y respaldo determinista.
  - **Detector de anomalías transaccionales** — *Isolation Forest* (scikit-learn) que
    puntúa cada pago y marca las transacciones atípicas para revisión.
  - **Agente conversacional** — patrón ReAct (LangGraph) que consulta el catálogo, el
    stock y los pedidos como **herramientas MCP**, con un circuit breaker sobre el LLM.
- **API Gateway (Traefik):** único punto de entrada, con validación de JWT y *rate limiting*.
- **Bus de eventos (RabbitMQ):** comunicación asíncrona *pub/sub* entre servicios.
- **Datos:** PostgreSQL (un esquema por servicio) + Redis (caché de respuestas del LLM y sesiones).
- **Frontend (React + TypeScript + Vite):** búsqueda, seguimiento de pedidos, chat con el
  agente y panel de operación.

En total, **15 contenedores** en ejecución con `docker compose`. El **autoescalado**
se demuestra sobre **k3s** (k3d) con *Horizontal Pod Autoscaler* y pruebas de carga con Locust.

## Requisitos

- **Docker Desktop** en ejecución (Docker Engine 24+ y Compose v2).
- Opcional, para desarrollar los servicios por separado: Python 3.11+, Poetry y Node 20+.
- Opcional, para el agente con LLM real: una clave gratuita de Google Gemini
  (sin clave, el agente responde con su respaldo determinista).

## Arranque rápido (Docker Compose)

```bash
cd infra
cp .env.example .env     # la primera vez (docker compose lee este archivo)
docker compose up -d     # levanta los 15 contenedores
docker compose ps        # verificar estado y healthchecks
```

Todo el tráfico entra por el gateway en **`http://localhost`** (Traefik, puerto 80).

| Acceso | URL | Credenciales (dev) |
|---|---|---|
| Frontend | http://localhost | usuario demo: `juan@shopia.demo` / `demo` |
| API (vía gateway) | http://localhost/api/... | JWT para rutas protegidas |
| Dashboard de Traefik | http://localhost:8080 | — |
| Consola de RabbitMQ | http://localhost:15672 | `pfi` / `pfi` |

Bajar todo: `docker compose down` (conserva datos) · `docker compose down -v` (borra los volúmenes).

> Guía detallada de accesos, puertos y un recorrido de prueba de punta a punta:
> [`docs/GUIA_DE_USO.md`](docs/GUIA_DE_USO.md).

### Rutas principales del gateway

| Ruta | Servicio | Auth |
|---|---|---|
| `GET /` | Frontend | público |
| `GET /api/catalogo/productos?q=` · `/{id}` | Catálogo (búsqueda / detalle) | público |
| `GET /api/stock/{id}` | Stock (disponibilidad) | público |
| `POST /api/auth/login` | Autenticación (emite JWT) | público |
| `POST /api/pedidos` · `GET /api/pedidos/{id}` · `GET /api/pedidos?usuario_id=` | Pedidos | JWT |
| `GET /api/pagos` | Pagos (pago simulado) | JWT |
| `POST /api/agente/chat` | Agente conversacional (ReAct + MCP) | JWT |
| `GET /api/anomalias/alertas` · `GET /api/notificaciones` | Alertas de fraude / notificaciones | JWT |

## Autoescalado sobre k3s

Para demostrar el escalado horizontal bajo carga se despliega el stack en un cluster
**k3s** (k3d) con el HPA configurado sobre Catálogo y Pedidos. Ver
[`k8s/README.md`](k8s/README.md) para el despliegue y [`load/README.md`](load/README.md)
para las pruebas de carga con Locust. Los scripts listos para usar están en
[`demo/`](demo/README.md).

## Pruebas

```bash
# Por servicio (desde la carpeta del servicio, con sus dependencias instaladas):
cd services/pedidos && pytest -q
```

La suite combina pruebas unitarias por servicio y pruebas funcionales de extremo a
extremo, con una cobertura de código agregada por encima del 90 %. Detalle en
[`tests/README.md`](tests/README.md). Los *benchmarks* de los módulos de IA
(detección de anomalías y agente) están en [`bench/README.md`](bench/README.md).

## Estructura del repositorio

```
.
├── infra/        docker-compose (PostgreSQL, Redis, RabbitMQ) + inicialización SQL
├── services/     microservicios (FastAPI): catálogo, stock, pedidos, usuarios, pagos,
│                 auth, notificaciones (IA) y anomalías (IA)
├── agent/        agente conversacional (ReAct) + servidor MCP de dominio
├── gateway/      configuración del API Gateway (Traefik): routing, JWT y rate limiting
├── front/        frontend (React + TypeScript + Vite)
├── k8s/          manifiestos de Kubernetes (k3s) + HPA para el autoescalado
├── load/         pruebas de carga con Locust
├── bench/        medición de los módulos de IA (anomalías y agente)
├── demo/         scripts de operación (levantar, resetear, prueba de carga)
├── tests/        pruebas funcionales de extremo a extremo
└── docs/         guía de uso
```

## Configuración

Las variables de entorno se definen en `infra/.env` (plantilla en `infra/.env.example`).
Las credenciales y secretos del ejemplo son **valores de desarrollo**; un despliegue real
debe reemplazarlos por secretos propios (base de datos, `JWT_SECRET`, clave del LLM).
