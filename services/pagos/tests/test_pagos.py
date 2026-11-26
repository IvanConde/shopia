"""Pruebas del servicio de Pagos: store (persistencia en Postgres, con sesión
simulada), consumidor (pago simulado) y endpoints. El bus (aio_pika), la BD y el
azar se sustituyen por dobles. Corre con asyncio.run.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import consumer, main, store


# --- Store (persistencia, sesión simulada) ---------------------------------
class Result:
    def __init__(self, rows): self._r = rows
    def scalars(self): return self
    def all(self): return self._r
    def scalar_one(self): return len(self._r)


class FakeSession:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.added = []
    def add(self, o): self.added.append(o)
    async def commit(self): pass
    async def execute(self, *a, **k): return Result(self.rows)
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


def test_store_registrar_persiste(monkeypatch):
    fake = FakeSession()
    monkeypatch.setattr(store, "SessionLocal", lambda: fake)
    asyncio.run(store.registrar_pago(
        {"pago_id": str(uuid.uuid4()), "pedido_id": str(uuid.uuid4()),
         "usuario_id": str(uuid.uuid4()), "monto": 74999, "estado": "completado"}))
    assert len(fake.added) == 1 and fake.added[0].estado == "completado"


def test_store_listar_mapea(monkeypatch):
    p = SimpleNamespace(id=uuid.uuid4(), pedido_id=uuid.uuid4(), usuario_id=uuid.uuid4(),
                        monto=74999, medio="simulado", estado="completado",
                        procesado_en=datetime.now(timezone.utc))
    monkeypatch.setattr(store, "SessionLocal", lambda: FakeSession(rows=[p]))
    out = asyncio.run(store.listar_pagos())
    assert out[0]["estado"] == "completado" and out[0]["monto"] == 74999.0


def test_store_total(monkeypatch):
    monkeypatch.setattr(store, "SessionLocal", lambda: FakeSession(rows=[1, 2, 3]))
    assert asyncio.run(store.total_procesados()) == 3


# --- Consumidor (pago simulado) --------------------------------------------
class _AProc:
    async def __aenter__(self): return None
    async def __aexit__(self, *a): return False


class FakeMessage:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def process(self): return _AProc()


@pytest.fixture(autouse=True)
def _dobles(monkeypatch):
    # Exchange del bus y persistencia simulados (no se toca RabbitMQ ni Postgres).
    monkeypatch.setattr(consumer, "_exchange", AsyncMock())
    monkeypatch.setattr(consumer, "registrar_pago", AsyncMock())
    yield


def _evento():
    return {"pedido_id": "22222222-2222-2222-2222-222222222222",
            "usuario_id": "11111111-1111-1111-1111-111111111111", "total": 74999}


def test_procesar_pago_aprobado(monkeypatch):
    monkeypatch.setattr(consumer.random, "random", lambda: 0.1)  # < prob_aprobado
    asyncio.run(consumer._procesar(FakeMessage(_evento())))
    assert consumer._exchange.publish.await_count >= 2
    consumer.registrar_pago.assert_awaited()


def test_procesar_pago_rechazado(monkeypatch):
    monkeypatch.setattr(consumer.random, "random", lambda: 0.99)  # > prob_aprobado
    asyncio.run(consumer._procesar(FakeMessage(_evento())))
    assert consumer._exchange.publish.await_count >= 2


def test_procesar_usa_hora_local_ar(monkeypatch):
    # la hora que viaja en `pagos.en_proceso` debe ser la local (UTC-3), no
    # la UTC; si fuera UTC, una compra de la tarde-noche caería en la "madrugada"
    # que el detector aprendió como anómala y dispararía falsos positivos.
    monkeypatch.setattr(consumer.random, "random", lambda: 0.1)
    asyncio.run(consumer._procesar(FakeMessage(_evento())))
    cuerpos = [json.loads(c.args[0].body) for c in consumer._exchange.publish.await_args_list]
    en_proceso = next(b for b in cuerpos if b.get("estado") == "en_proceso")
    assert en_proceso["hora"] == datetime.now(consumer._TZ_AR).hour


def test_iniciar_y_detener(monkeypatch):
    conn = AsyncMock(); chan = AsyncMock()
    conn.channel.return_value = chan
    chan.declare_exchange.return_value = AsyncMock()
    chan.declare_queue.return_value = AsyncMock()

    async def fake_connect(url): return conn
    monkeypatch.setattr(consumer.aio_pika, "connect_robust", fake_connect)
    asyncio.run(consumer.iniciar_consumidor())
    asyncio.run(consumer.detener_consumidor())


# --- Endpoints --------------------------------------------------------------
def test_health_incluye_contador(monkeypatch):
    monkeypatch.setattr(main, "total_procesados", AsyncMock(return_value=0))
    r = asyncio.run(main.health())
    assert r["service"] == "pagos" and "pagos_procesados" in r


def test_endpoint_pagos_lista(monkeypatch):
    monkeypatch.setattr(main, "listar_pagos", AsyncMock(return_value=[]))
    assert isinstance(asyncio.run(main.pagos()), list)
