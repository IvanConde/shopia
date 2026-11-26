"""Pruebas funcionales de seguridad del gateway (JWT en el borde + rate limiting).

Van al final (nombre alfabético) porque el test de rate limiting satura el
limitador a propósito; correrlo antes podría afectar a los demás.
"""

import time

from conftest import USUARIO_DEMO


def test_ruta_protegida_sin_token_da_401(cliente):
    r = cliente.get("/api/pedidos", params={"usuario_id": USUARIO_DEMO})
    assert r.status_code == 401


def test_ruta_protegida_con_token_da_200(cliente, headers):
    r = cliente.get("/api/pedidos", params={"usuario_id": USUARIO_DEMO}, headers=headers)
    assert r.status_code == 200


def test_ruta_publica_no_requiere_token(cliente, producto):
    # Catálogo y stock son públicos (consulta de disponibilidad).
    assert cliente.get("/api/catalogo/productos", params={"q": "aura"}).status_code == 200
    assert cliente.get(f"/api/stock/{producto['id']}").status_code == 200


def test_rate_limiting_devuelve_429(cliente, producto):
    """Una ráfaga por encima del límite del gateway produce 429."""
    ruta = f"/api/stock/{producto['id']}"
    codigos = [cliente.get(ruta).status_code for _ in range(120)]
    assert 429 in codigos, "no se activó el rate limiting"
    assert 200 in codigos, "el limitador no dejó pasar ninguna petición"
    # Deja recuperar el bucket para no interferir si se reejecuta la suite.
    time.sleep(2)
