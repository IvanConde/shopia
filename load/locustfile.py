"""Pruebas de carga del prototipo con Locust.

Simula el patrón de tráfico de un pico tipo CyberMonday: mayoría de usuarios
**navegando** (lecturas de catálogo y stock, que es lo que escala horizontalmente)
y una fracción menor **comprando** (checkout autenticado).

El agente conversacional (`ConversadorAgente`) está **desactivado por defecto**
(peso 0): cada consulta gasta cuota del free tier de Gemini, así que no conviene
martillarlo en una corrida larga. Se puede activar de forma acotada para evaluar
el patrón MCP bajo carga (brecha) con la variable `AGENTE_CARGA_WEIGHT`.

Uso rápido (web UI en http://localhost:8089):
    locust -f locustfile.py --host http://127.0.0.1
Headless (100 usuarios, +10/s, 2 min):
    locust -f locustfile.py --host http://127.0.0.1 --headless -u 100 -r 10 -t 2m
Incluir carga del agente (peso 1, acotado por la cuota de Gemini):
    AGENTE_CARGA_WEIGHT=1 locust -f locustfile.py --host http://127.0.0.1 --headless -u 20 -r 2 -t 1m

IMPORTANTE — rate limiting: el gateway limita a ~20 req/s por IP (D6). Para una
prueba de **capacidad** (apuntar a ~300 RPS) hay que subir/desactivar ese
límite primero (ver README.md), o el test medirá el limitador y no el sistema.
"""

import os
import random
import uuid

from locust import HttpUser, between, task

# Usuario con cuenta real (sólo para obtener un JWT válido del gateway). OJO: el
# comprador simulado NO crea los pedidos a nombre de este usuario, sino de un
# cliente sintético distinto por sesión (ver Comprador.on_start). Así la cuenta
# de la demo (Juan) queda limpia: sólo ve sus propias compras manuales, y el
# tráfico de la prueba de carga no le contamina el historial ni las notificaciones.
USUARIO_DEMO = os.environ.get("USUARIO_DEMO_ID", "11111111-1111-1111-1111-111111111111")
EMAIL = os.environ.get("DEMO_EMAIL", "juan@shopia.demo")
PASSWORD = os.environ.get("DEMO_PASSWORD", "demo")
TERMINOS = ["aura", "auriculares", "nova", "teclado", "mouse", "parlante", "pro", "lite"]
# Peso de la carga del agente (0 = desactivado; gasta cuota de Gemini). Opt-in.
PESO_AGENTE = int(os.environ.get("AGENTE_CARGA_WEIGHT", "0"))
CONSULTAS_AGENTE = [
    "quiero auriculares aura", "busco un teclado", "mostrame mouse",
    "necesito un parlante", "hay notebooks", "qué modelos de aura tienen",
]


def _ids_de_productos(client) -> list[str]:
    """Trae los ids del catálogo una vez, para variar las consultas de stock."""
    with client.get("/api/catalogo/productos", name="/api/catalogo/productos [seed]",
                     catch_response=True) as r:
        if r.status_code == 200:
            return [p["id"] for p in r.json()]
        r.failure(f"catálogo devolvió {r.status_code}")
        return []


class Navegante(HttpUser):
    """Mayoría del tráfico: navega catálogo y consulta stock (público, read-heavy)."""

    weight = 3
    wait_time = between(1, 3)

    def on_start(self):
        self.productos = _ids_de_productos(self.client)

    @task(4)
    def buscar_catalogo(self):
        self.client.get("/api/catalogo/productos", params={"q": random.choice(TERMINOS)},
                        name="/api/catalogo/productos?q=")

    @task(2)
    def ver_stock(self):
        if self.productos:
            self.client.get(f"/api/stock/{random.choice(self.productos)}", name="/api/stock/{id}")


class Comprador(HttpUser):
    """Fracción menor: usuario autenticado que consulta su historial y compra."""

    weight = 1
    wait_time = between(2, 5)

    def on_start(self):
        self.token = None
        self.productos = _ids_de_productos(self.client)
        # Cada comprador simulado es un cliente sintético distinto: así el pico se
        # reparte entre muchos usuarios (realista) y NO se mezcla con la cuenta de
        # la demo (Juan). El perfil de estos ids no existe en Usuarios, así que el
        # motor de notificaciones los trata con su segmento por defecto (no rompe).
        self.uid = str(uuid.uuid4())
        with self.client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD},
                              name="/api/auth/login", catch_response=True) as r:
            if r.status_code == 200:
                self.token = r.json()["access_token"]
            else:
                r.failure(f"login devolvió {r.status_code}")

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(3)
    def ver_historial(self):
        self.client.get("/api/pedidos", params={"usuario_id": self.uid},
                        headers=self._headers, name="/api/pedidos [historial]")

    @task(1)
    def comprar(self):
        if self.token and self.productos:
            self.client.post(
                "/api/pedidos", headers=self._headers,
                json={"usuario_id": self.uid,
                      "items": [{"producto_id": random.choice(self.productos), "cantidad": 1}]},
                name="/api/pedidos [crear]",
            )


class ConversadorAgente(HttpUser):
    """Carga del agente conversacional (patrón MCP) bajo tráfico. DESACTIVADA por
    defecto (peso 0) porque consume cuota del free tier de Gemini: activar con
    `AGENTE_CARGA_WEIGHT` o seleccionando esta clase explícitamente en la CLI."""

    weight = PESO_AGENTE
    wait_time = between(2, 6)

    def on_start(self):
        self.token = None
        with self.client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD},
                              name="/api/auth/login", catch_response=True) as r:
            if r.status_code == 200:
                self.token = r.json()["access_token"]
            else:
                r.failure(f"login devolvió {r.status_code}")
        # Sesión de memoria por usuario simulado, para no mezclar hilos.
        self.session_id = f"load-{random.randint(1, 10_000_000)}"

    @task
    def conversar(self):
        if not self.token:
            return
        self.client.post(
            "/api/agente/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"mensaje": random.choice(CONSULTAS_AGENTE), "session_id": self.session_id},
            name="/api/agente/chat",
        )
