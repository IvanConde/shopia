"""Pruebas del servicio Stock: endpoints, seed y el ciclo de reserva del consumidor
(reserva / confirma / libera / sin_stock). Bus y BD simulados. Corre con asyncio.run.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app import consumer, main, seed


# --- Dobles -----------------------------------------------------------------
class Result:
    def __init__(self, items): self._i = items
    def scalars(self): return self
    def all(self): return self._i


class FakeSession:
    def __init__(self, stock=None, reservas=None):
        self._stock = stock
        self._reservas = reservas or []
        self.added = []
    def add(self, o): self.added.append(o)
    async def commit(self): pass
    async def get(self, model, id): return self._stock
    async def execute(self, *a, **k): return Result(self._reservas)
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class _AProc:
    async def __aenter__(self): return None
    async def __aexit__(self, *a): return False


class FakeMessage:
    def __init__(self, body, rk):
        self.body = json.dumps(body).encode()
        self.routing_key = rk
    def process(self): return _AProc()


PED = "22222222-2222-2222-2222-222222222222"
PRO = "33333333-3333-3333-3333-333333333333"


# --- Endpoints --------------------------------------------------------------
def test_health():
    assert asyncio.run(main.health())["service"] == "stock"


def test_listar():
    assert asyncio.run(main.listar(FakeSession())) == []


def test_obtener_404():
    with pytest.raises(HTTPException):
        asyncio.run(main.obtener("id", FakeSession(stock=None)))


def test_obtener_ok():
    s = object()
    assert asyncio.run(main.obtener("id", FakeSession(stock=s))) is s


# --- Consumidor: reserva ----------------------------------------------------
def test_reservar_descuenta(monkeypatch):
    stock = SimpleNamespace(disponible=50, reservado=0)
    sess = FakeSession(stock=stock)
    monkeypatch.setattr(consumer, "SessionLocal", lambda: sess)
    monkeypatch.setattr(consumer, "_exchange", AsyncMock())
    asyncio.run(consumer._reservar({"pedido_id": PED, "items": [{"producto_id": PRO, "cantidad": 3}]}))
    assert stock.disponible == 47 and stock.reservado == 3 and sess.added


def test_reservar_sin_stock_publica(monkeypatch):
    stock = SimpleNamespace(disponible=1, reservado=0)
    monkeypatch.setattr(consumer, "SessionLocal", lambda: FakeSession(stock=stock))
    monkeypatch.setattr(consumer, "_exchange", AsyncMock())
    asyncio.run(consumer._reservar({"pedido_id": PED, "items": [{"producto_id": PRO, "cantidad": 9999}]}))
    consumer._exchange.publish.assert_awaited()  # stock.sin_stock
    assert stock.disponible == 1  # no se descuenta


# --- Consumidor: confirmar / liberar ---------------------------------------
def _reserva():
    return SimpleNamespace(producto_id=PRO, cantidad=2, estado="reservada")


def test_confirmar_reserva(monkeypatch):
    stock = SimpleNamespace(disponible=48, reservado=2)
    reserva = _reserva()
    monkeypatch.setattr(consumer, "SessionLocal", lambda: FakeSession(stock=stock, reservas=[reserva]))
    asyncio.run(consumer._resolver_reservas(PED, confirmar=True))
    assert reserva.estado == "confirmada" and stock.reservado == 0 and stock.disponible == 48


def test_liberar_reserva(monkeypatch):
    stock = SimpleNamespace(disponible=48, reservado=2)
    reserva = _reserva()
    monkeypatch.setattr(consumer, "SessionLocal", lambda: FakeSession(stock=stock, reservas=[reserva]))
    asyncio.run(consumer._resolver_reservas(PED, confirmar=False))
    assert reserva.estado == "liberada" and stock.reservado == 0 and stock.disponible == 50


# --- Consumidor: dispatch + conexión ---------------------------------------
def test_procesar_despacha_por_routing_key(monkeypatch):
    monkeypatch.setattr(consumer, "_reservar", AsyncMock())
    monkeypatch.setattr(consumer, "_resolver_reservas", AsyncMock())
    asyncio.run(consumer._procesar(FakeMessage({"pedido_id": PED, "items": []}, "pedidos.creados")))
    asyncio.run(consumer._procesar(FakeMessage({"pedido_id": PED}, "pagos.completados")))
    asyncio.run(consumer._procesar(FakeMessage({"pedido_id": PED}, "pagos.rechazados")))
    assert consumer._reservar.await_count == 1
    assert consumer._resolver_reservas.await_count == 2


def test_iniciar_y_detener(monkeypatch):
    conn = AsyncMock(); chan = AsyncMock()
    conn.channel.return_value = chan
    chan.declare_exchange.return_value = AsyncMock()
    chan.declare_queue.return_value = AsyncMock()

    async def fc(url): return conn
    monkeypatch.setattr(consumer.aio_pika, "connect_robust", fc)
    asyncio.run(consumer.iniciar_consumidor())
    asyncio.run(consumer.detener_consumidor())


def test_conectar_reintenta(monkeypatch):
    estado = {"n": 0}; conn = AsyncMock()

    async def flaky(url):
        estado["n"] += 1
        if estado["n"] < 2:
            raise ConnectionError("x")
        return conn
    monkeypatch.setattr(consumer.aio_pika, "connect_robust", flaky)
    monkeypatch.setattr(consumer.asyncio, "sleep", AsyncMock())
    assert asyncio.run(consumer._conectar()) is conn


# --- Seed -------------------------------------------------------------------
def test_sembrar_stock(monkeypatch):
    class Resp:
        def raise_for_status(self): pass
        def json(self): return [{"id": PRO}]

    class Client:
        def __init__(self, **k): pass
        async def get(self, url): return Resp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(seed.httpx, "AsyncClient", lambda **k: Client())
    añadidos = []

    class S:
        async def get(self, model, id): return None  # no existe → se crea
        def add(self, o): añadidos.append(o)
        async def commit(self): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(seed, "SessionLocal", lambda: S())
    asyncio.run(seed.sembrar_stock())
    assert len(añadidos) == 1
