# Pruebas del prototipo

Dos capas de pruebas que cubren el desarrollo funcional del prototipo:

## 1. Pruebas funcionales end-to-end (esta carpeta)

Ejercitan el sistema **en marcha**, atravesando el API Gateway igual que el frontend. Cubren:

- **Flujo de compra** (`test_flujo_compra.py`): búsqueda pública, alta de pedido, cierre del lazo del pago (estado `pagado`/`pendiente_de_pago`) y consistencia del stock (reserva → confirma/libera).
- **Módulos de IA** (`test_modulos_ia.py`): respuesta del agente con traza (MCP/ReAct), detección de anomalías (alerta ante monto atípico) y notificación adaptativa generada.
- **Seguridad del gateway** (`test_seguridad_gateway.py`): JWT en el borde (401 sin token / 200 con token), rutas públicas y **rate limiting** (429 ante ráfaga).

**Requisitos:** el stack levantado (`cd infra && docker compose up -d`) y `pytest` + `httpx`.

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install pytest httpx
cd tests
pytest -v
```

Variables opcionales: `GATEWAY_URL` (def. `http://127.0.0.1`), `ANOMALIAS_URL` (`:8007`), `NOTIFICACIONES_URL` (`:8008`).

## 2. Pruebas unitarias (dentro de cada servicio)

Lógica pura, sin infraestructura. Viven junto al servicio y usan sus propias dependencias:

- `services/anomalias/tests/test_detector.py` — el Isolation Forest distingue montos normales de atípicos.
- `services/notificaciones/tests/test_guardrails.py` — los guardrails validan/sanean la salida del LLM.

Se corren en el entorno del servicio (donde están sus dependencias), por ejemplo dentro del contenedor:

```bash
docker cp services/anomalias/tests pfi-anomalias:/srv/tests
docker exec pfi-anomalias sh -c "pip install -q pytest && cd /srv && python -m pytest tests -v"
```

(análogo para `notificaciones`).
