# services/ — Microservicios de dominio

Un microservicio por carpeta (Python + FastAPI, deps con Poetry). Cada uno es
dueño de su esquema en PostgreSQL y se comunica por HTTP (síncrono, vía gateway)
y por eventos RabbitMQ (asíncrono).

Orden de arranque previsto para la demo del 50%: **Catálogo** y **Pedidos**.

Estructura sugerida por servicio:

```
services/catalogo/
  pyproject.toml        # deps con Poetry
  Dockerfile
  app/
    main.py             # FastAPI + routers
    ...
```

Cuando exista el primer servicio, se agregará como un `service` más en
`infra/docker-compose.yml`, conectado a la red `pfi_net`.
