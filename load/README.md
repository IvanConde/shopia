# Pruebas de carga (Locust)

Andamiaje para las pruebas de carga y de escalabilidad del prototipo. Simula un pico tipo CyberMonday: mayoría navegando (lecturas de
catálogo/stock) y una fracción comprando (checkout autenticado).

> **Estado:** los scripts corren contra `docker compose` (métricas de throughput y
> latencia) y contra **k3s/k3d**, donde ya se demostró el **autoescalado** (HPA
> 1→5→1 bajo carga; ver `k8s/`). El mismo
> `locustfile.py` sirve para ambos entornos: solo cambia el `--host`.

## Requisitos

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Correr

Con interfaz web (recomendado para explorar; UI en http://localhost:8089):

```bash
cd load
locust -f locustfile.py --host http://127.0.0.1
```

Sin interfaz (reproducible; 100 usuarios, +10/s, 2 minutos, reporte HTML):

```bash
locust -f locustfile.py --host http://127.0.0.1 \
       --headless -u 100 -r 10 -t 2m --html reporte.html
```

## ⚠️ Rate limiting: subir el límite para medir capacidad

El gateway limita a ~**20 req/s por IP** (middleware `ratelimit`, D6). Eso es
correcto en producción, pero **tapa** una prueba de capacidad: si apuntás a los
~300 RPS del objetivo, casi todo devolvería **429** y estarías midiendo
el limitador, no el sistema. Para el load test, elegí una:

1. **Subir el umbral** en `gateway/dynamic.yml` (middleware `ratelimit`,
   p. ej. `average: 1000`, `burst: 2000`) y **reiniciar el gateway**
   (`docker compose restart gateway` — en Windows el file-watch no recarga solo).
   Volver a bajarlo al terminar.
2. **Apuntar a un servicio directo**, salteando el gateway
   (`--host http://127.0.0.1:8001` para Catálogo), útil para aislar la capacidad
   de un microservicio puntual.

## Notas

- El **agente** (`/api/agente/chat`, clase `ConversadorAgente`) está **desactivado
  por defecto** (peso 0): cada consulta gasta cuota del free tier de Gemini. Para
  evaluar el patrón MCP bajo carga de forma acotada, activarlo con
  `AGENTE_CARGA_WEIGHT=1` y pocos usuarios/tiempo. La medición puntual del agente
  (latencia y acierto) está en `bench/medir_oe3_agente.py`.
- Un checkout dispara toda la cadena de eventos (Pagos → Pedidos/Stock/Anomalías/
  Notificaciones), así que la carga ejercita el sistema completo, no solo la HTTP.
- Objetivo de referencia: ~500 usuarios concurrentes / ~300 RPS con
  p99 < 500 ms; cifra inicial, **a calibrar tras el primer load test**.
