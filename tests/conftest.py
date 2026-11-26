"""Fixtures compartidas para las pruebas funcionales end-to-end del prototipo.

Estas pruebas se ejecutan contra el **stack en marcha** (docker compose up),
atravesando el API Gateway igual que lo haría el frontend. Requieren únicamente
`pytest` y `httpx`. Ver README.md para cómo correrlas.
"""

import os
import time

import httpx
import pytest

# El gateway (único punto de entrada). Los servicios de IA no están tras el
# gateway, así que se consultan por su puerto directo (solo para inspección).
GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1")
ANOMALIAS = os.environ.get("ANOMALIAS_URL", "http://127.0.0.1:8007")
NOTIFICACIONES = os.environ.get("NOTIFICACIONES_URL", "http://127.0.0.1:8008")

USUARIO_DEMO = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(scope="session")
def cliente():
    with httpx.Client(base_url=GATEWAY, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session")
def token(cliente):
    r = cliente.post("/api/auth/login", json={"email": "juan@shopia.demo", "password": "demo"})
    assert r.status_code == 200, f"login falló: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def producto(cliente):
    """Primer producto del catálogo que matchea 'aura' (dato sembrado)."""
    r = cliente.get("/api/catalogo/productos", params={"q": "aura"})
    assert r.status_code == 200
    productos = r.json()
    assert productos, "el catálogo no devolvió productos para 'aura'"
    return productos[0]


def crear_pedido(cliente, headers, producto_id, cantidad=1):
    r = cliente.post(
        "/api/pedidos",
        headers=headers,
        json={"usuario_id": USUARIO_DEMO, "items": [{"producto_id": producto_id, "cantidad": cantidad}]},
    )
    assert r.status_code == 201, f"crear pedido falló: {r.status_code} {r.text}"
    return r.json()


def esperar_estado_final(cliente, headers, pedido_id, timeout=8.0):
    """Espera a que el pedido salga de 'creado' (lo resuelve el pago, asíncrono)."""
    fin = time.time() + timeout
    while time.time() < fin:
        r = cliente.get(f"/api/pedidos/{pedido_id}", headers=headers)
        if r.status_code == 200 and r.json()["estado"] != "creado":
            return r.json()["estado"]
        time.sleep(0.3)
    return "creado"
