"""Pruebas del consumidor y los endpoints del detector de anomalías.

Se ejercita la lógica sin bus ni base de datos reales: RabbitMQ (aio_pika) y la
sesión de SQLAlchemy se sustituyen por dobles de prueba. Las corrutinas se corren
con asyncio.run (no hace falta pytest-asyncio).
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app import consumer, detector, main


# --- Dobles de prueba -------------------------------------------------------
class _AProc:
    async def __aenter__(self): return None
    async def __aexit__(self, *a): return False


class FakeMessage:
    def __init__(self, body, rk="pagos.en_proceso"):
        self.body = json.dumps(body).encode()
        self.routing_key = rk

    def process(self): return _AProc()


class FakeSession:
    def __init__(self): self.added = []
    def add(self, o): self.added.append(o)
    async def commit(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    detector.entrenar()
    monkeypatch.setattr(consumer, "_exchange", AsyncMock())
    monkeypatch.setattr(consumer, "SessionLocal", lambda: FakeSession())
    yield


# --- Consumidor -------------------------------------------------------------
def test_procesar_normal_no_persiste_ni_publica():
    msg = FakeMessage({"pago_id": "p1", "pedido_id": "pe1", "usuario_id": "u1", "monto": 75000})
    asyncio.run(consumer._procesar(msg))
    consumer._exchange.publish.assert_not_awaited()


def test_procesar_anomalia_persiste_y_publica():
    msg = FakeMessage({
        "pago_id": "11111111-1111-1111-1111-111111111111",
        "pedido_id": "22222222-2222-2222-2222-222222222222",
        "usuario_id": "33333333-3333-3333-3333-333333333333",
        "monto": 9_000_000,
    })
    asyncio.run(consumer._procesar(msg))
    consumer._exchange.publish.assert_awaited()


def test_procesar_sin_campos_se_ignora():
    asyncio.run(consumer._procesar(FakeMessage({"monto": 100})))  # falta pago_id
    consumer._exchange.publish.assert_not_awaited()


def test_contadores_expone_metricas():
    assert set(consumer.contadores()) == {"evaluadas", "anomalias"}


def test_iniciar_y_detener_consumidor(monkeypatch):
    conn = AsyncMock()
    chan = AsyncMock()
    conn.channel.return_value = chan
    chan.declare_exchange.return_value = AsyncMock()
    chan.declare_queue.return_value = AsyncMock()

    async def fake_connect(url): return conn
    monkeypatch.setattr(consumer.aio_pika, "connect_robust", fake_connect)
    asyncio.run(consumer.iniciar_consumidor())
    asyncio.run(consumer.detener_consumidor())


def test_conectar_reintenta_si_rabbit_no_esta(monkeypatch):
    estado = {"n": 0}
    conn = AsyncMock()

    async def flaky(url):
        estado["n"] += 1
        if estado["n"] < 2:
            raise ConnectionError("rabbit no está")
        return conn

    monkeypatch.setattr(consumer.aio_pika, "connect_robust", flaky)
    monkeypatch.setattr(consumer.asyncio, "sleep", AsyncMock())
    assert asyncio.run(consumer._conectar()) is conn


# --- Endpoints --------------------------------------------------------------
def test_health():
    r = asyncio.run(main.health())
    assert r["service"] == "anomalias" and r["status"] == "ok"


def test_alertas_lista_vacia(monkeypatch):
    class Result:
        def scalars(self): return self
        def all(self): return []

    class S:
        async def execute(self, *a, **k): return Result()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    monkeypatch.setattr(main, "SessionLocal", lambda: S())
    assert asyncio.run(main.alertas(x_user_id=None)) == []
