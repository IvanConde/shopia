"""Pruebas de las herramientas del servidor MCP de dominio. Se simula la llamada
HTTP a Catálogo/Pedidos mockeando `_get`. Corre con asyncio.run.
"""

import asyncio
from unittest.mock import AsyncMock

from app import server


class Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._p = payload
    def json(self): return self._p


# Las funciones pueden quedar envueltas por @mcp.tool(); se obtiene el callable real.
def _fn(tool):
    return getattr(tool, "fn", tool)


def test_buscar_productos_ok(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(
        200, [{"id": "1", "nombre": "Aura", "descripcion": "d", "precio": 10}])))
    r = asyncio.run(_fn(server.buscar_productos)("aura"))
    assert r[0]["nombre"] == "Aura" and r[0]["precio"] == 10


def test_buscar_productos_error(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(500)))
    r = asyncio.run(_fn(server.buscar_productos)("x"))
    assert "error" in r[0]


# Las tools de pedidos reciben `ctx` (contexto FastMCP) para reenviar X-User-Id;
# en las pruebas se pasa None, que el helper _reenvio_dueno tolera (sin reenvío).
def test_estado_pedido_ok(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(
        200, {"id": "p1", "estado": "pagado", "total": 100, "fecha_estimada": "2026-10-10",
              "items": [{"x": 1}]})))
    r = asyncio.run(_fn(server.consultar_estado_pedido)("p1", None))
    assert r["estado"] == "pagado" and r["cantidad_items"] == 1


def test_estado_pedido_404(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(404)))
    r = asyncio.run(_fn(server.consultar_estado_pedido)("p1", None))
    assert "error" in r


def test_estado_pedido_error(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(503)))
    assert "error" in asyncio.run(_fn(server.consultar_estado_pedido)("p1", None))


def test_historial_ok(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(
        200, [{"id": "p1", "estado": "pagado", "total": 100, "creado_en": "2026-10-04"}])))
    r = asyncio.run(_fn(server.historial_pedidos)("u1", None))
    assert r[0]["pedido_id"] == "p1"


def test_historial_error(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(500)))
    assert "error" in asyncio.run(_fn(server.historial_pedidos)("u1", None))[0]


def test_consultar_stock_ok(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(
        200, {"producto_id": "p1", "disponible": 5, "reservado": 1})))
    r = asyncio.run(_fn(server.consultar_stock)("p1"))
    assert r["disponible"] == 5 and r["hay_stock"] is True


def test_consultar_stock_sin_stock(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(
        200, {"producto_id": "p1", "disponible": 0, "reservado": 0})))
    r = asyncio.run(_fn(server.consultar_stock)("p1"))
    assert r["hay_stock"] is False


def test_consultar_stock_404(monkeypatch):
    monkeypatch.setattr(server, "_get", AsyncMock(return_value=Resp(404)))
    assert "error" in asyncio.run(_fn(server.consultar_stock)("p1"))


def test_health():
    r = asyncio.run(server.health(None))
    assert r.status_code == 200
