"""Pruebas del servicio Pedidos: endpoints (checkout/seguimiento/historial),
cliente de Catálogo, eventos y el consumidor que cierra el lazo del pago.
BD, HTTP y bus simulados. Corre con asyncio.run.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app import catalogo_client, consumer, events, main
from app.schemas import ItemPedidoIn, PedidoCreate

USR = "11111111-1111-1111-1111-111111111111"
PRO = "33333333-3333-3333-3333-333333333333"
PED = "22222222-2222-2222-2222-222222222222"


class Result:
    def __init__(self, items): self._i = items
    def scalars(self): return self
    def all(self): return self._i


class FakeSession:
    def __init__(self, items=None, obj=None):
        self._items = items or []
        self._obj = obj
        self.added = []
    def add(self, o): self.added.append(o)
    async def commit(self): pass
    async def refresh(self, o): pass
    async def execute(self, *a, **k): return Result(self._items)
    async def get(self, model, id): return self._obj


class _AProc:
    async def __aenter__(self): return None
    async def __aexit__(self, *a): return False


class FakeMessage:
    def __init__(self, body, rk):
        self.body = json.dumps(body).encode()
        self.routing_key = rk
    def process(self): return _AProc()


# --- Endpoints --------------------------------------------------------------
def test_health():
    assert asyncio.run(main.health())["service"] == "pedidos"


def test_crear_pedido_ok(monkeypatch):
    monkeypatch.setattr(main, "obtener_producto", AsyncMock(return_value={"precio": 1000}))
    monkeypatch.setattr(main, "publicar_evento", AsyncMock())
    body = PedidoCreate(usuario_id=USR, items=[ItemPedidoIn(producto_id=PRO, cantidad=2)])
    ped = asyncio.run(main.crear_pedido(body, FakeSession()))
    assert ped.estado == "creado" and ped.total == 1000 * 2
    main.publicar_evento.assert_awaited()


def test_crear_pedido_producto_inexistente(monkeypatch):
    monkeypatch.setattr(main, "obtener_producto", AsyncMock(return_value=None))
    body = PedidoCreate(usuario_id=USR, items=[ItemPedidoIn(producto_id=PRO, cantidad=1)])
    with pytest.raises(HTTPException):
        asyncio.run(main.crear_pedido(body, FakeSession()))


def test_consultar_404():
    with pytest.raises(HTTPException):
        asyncio.run(main.consultar_pedido("id", FakeSession(obj=None), x_user_id=None))


def test_consultar_ok():
    # Llamada interna (sin X-User-Id): no se restringe por dueño.
    o = object()
    assert asyncio.run(main.consultar_pedido("id", FakeSession(obj=o), x_user_id=None)) is o


def test_consultar_propio_ok():
    # con X-User-Id del dueño, devuelve el pedido.
    ped = SimpleNamespace(usuario_id=USR)
    assert asyncio.run(main.consultar_pedido("id", FakeSession(obj=ped), x_user_id=USR)) is ped


def test_consultar_ajeno_404():
    # un pedido de otro usuario responde 404 (no revela su existencia).
    ped = SimpleNamespace(usuario_id=USR)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.consultar_pedido("id", FakeSession(obj=ped),
                                          x_user_id="22222222-2222-2222-2222-222222222222"))
    assert exc.value.status_code == 404


def test_historial_interno():
    # Sin header: uso interno, filtra por el usuario_id del query.
    assert asyncio.run(main.historial_pedidos(USR, FakeSession([]), x_user_id=None)) == []


def test_historial_por_token():
    # con X-User-Id, el historial usa el dueño del token.
    assert asyncio.run(main.historial_pedidos(None, FakeSession([]), x_user_id=USR)) == []


def test_historial_token_invalido():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.historial_pedidos(None, FakeSession([]), x_user_id="no-uuid"))
    assert exc.value.status_code == 401


def test_historial_sin_identificador():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.historial_pedidos(None, FakeSession([]), x_user_id=None))
    assert exc.value.status_code == 400


# --- Cliente de Catálogo ----------------------------------------------------
def _client_con(status, payload=None):
    class Resp:
        status_code = status
        def raise_for_status(self): pass
        def json(self): return payload

    class Client:
        def __init__(self, **k): pass
        async def get(self, url): return Resp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    return lambda **k: Client()


def test_obtener_producto_ok(monkeypatch):
    monkeypatch.setattr(catalogo_client.httpx, "AsyncClient", _client_con(200, {"id": PRO, "precio": 1}))
    assert asyncio.run(catalogo_client.obtener_producto(PRO))["precio"] == 1


def test_obtener_producto_404(monkeypatch):
    monkeypatch.setattr(catalogo_client.httpx, "AsyncClient", _client_con(404))
    assert asyncio.run(catalogo_client.obtener_producto(PRO)) is None


def test_catalogo_breaker_abre_y_falla_rapido(monkeypatch):
    # errores de red cuentan fallos; tras N, el circuito abre y falla ya.
    class Boom:
        def __init__(self, **k): pass
        async def get(self, url): raise catalogo_client.httpx.ConnectError("catálogo caído")
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(catalogo_client.httpx, "AsyncClient", lambda **k: Boom())
    cb = catalogo_client._breaker
    cb.registrar_exito()  # parte cerrado
    for _ in range(cb.umbral_fallos):
        with pytest.raises(catalogo_client.CatalogoNoDisponible):
            asyncio.run(catalogo_client.obtener_producto(PRO))
    assert cb.estado == "abierto"
    cb.registrar_exito()  # reset para no afectar otras pruebas


def test_crear_pedido_catalogo_no_disponible(monkeypatch):
    monkeypatch.setattr(main, "obtener_producto",
                        AsyncMock(side_effect=main.CatalogoNoDisponible("caído")))
    body = PedidoCreate(usuario_id=USR, items=[ItemPedidoIn(producto_id=PRO, cantidad=1)])
    with pytest.raises(HTTPException) as e:
        asyncio.run(main.crear_pedido(body, FakeSession()))
    assert e.value.status_code == 503


# --- Eventos ----------------------------------------------------------------
def test_publicar_evento_ok_y_degrada(monkeypatch):
    exch = AsyncMock(); chan = AsyncMock(); chan.declare_exchange.return_value = exch
    conn = AsyncMock(); conn.channel.return_value = chan

    async def ok(url): return conn
    monkeypatch.setattr(events.aio_pika, "connect_robust", ok)
    assert asyncio.run(events.publicar_evento("pedidos.creados", {"a": 1})) is True
    asyncio.run(events.cerrar_conexion())

    async def boom(url): raise RuntimeError("sin bus")
    monkeypatch.setattr(events.aio_pika, "connect_robust", boom)
    assert asyncio.run(events.publicar_evento("pedidos.creados", {})) is False


# --- Consumidor: cierre del lazo del pago -----------------------------------
def test_consumidor_marca_pagado(monkeypatch):
    pedido = SimpleNamespace(estado="creado")

    class S(FakeSession):
        async def get(self, model, id): return pedido
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(consumer, "SessionLocal", lambda: S())
    asyncio.run(consumer._procesar(FakeMessage({"pedido_id": PED}, "pagos.completados")))
    assert pedido.estado == "pagado"


def test_consumidor_marca_pendiente(monkeypatch):
    pedido = SimpleNamespace(estado="creado")

    class S(FakeSession):
        async def get(self, model, id): return pedido
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(consumer, "SessionLocal", lambda: S())
    asyncio.run(consumer._procesar(FakeMessage({"pedido_id": PED}, "pagos.rechazados")))
    assert pedido.estado == "pendiente_de_pago"


def test_consumidor_pedido_inexistente(monkeypatch):
    class S(FakeSession):
        async def get(self, model, id): return None
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(consumer, "SessionLocal", lambda: S())
    asyncio.run(consumer._procesar(FakeMessage({"pedido_id": PED}, "pagos.completados")))


def test_consumidor_evento_desconocido():
    # routing key sin mapeo ni pedido_id → se ignora sin tocar la BD
    asyncio.run(consumer._procesar(FakeMessage({}, "pagos.en_proceso")))


def test_iniciar_y_detener(monkeypatch):
    conn = AsyncMock(); chan = AsyncMock()
    conn.channel.return_value = chan
    chan.declare_exchange.return_value = AsyncMock()
    chan.declare_queue.return_value = AsyncMock()

    async def fc(url): return conn
    monkeypatch.setattr(consumer.aio_pika, "connect_robust", fc)
    asyncio.run(consumer.iniciar_consumidor())
    asyncio.run(consumer.detener_consumidor())


# --- Vista de vendedor (resumen de operación) -------------------------------
def _ped(estado, total, items_cants, creado=None):
    its = [SimpleNamespace(cantidad=c) for c in items_cants]
    return SimpleNamespace(id=PED, estado=estado, total=Decimal(str(total)),
                           creado_en=creado or datetime.now(timezone.utc), items=its)


def test_resumen_vendedor(monkeypatch):
    # El conteo de fraude consulta a Anomalías por HTTP → se mockea.
    monkeypatch.setattr(main, "_contar_pedidos_en_revision", AsyncMock(return_value=2))
    peds = [
        _ped("pagado", 1000, [1, 2]),          # 3 ítems, suma ingresos
        _ped("pagado", 500, [1]),              # 1 ítem, suma ingresos
        _ped("pendiente_de_pago", 300, [1]),   # no suma ingresos
    ]
    res = asyncio.run(main.resumen_vendedor(FakeSession(peds)))
    assert res["pedidos_total"] == 3
    assert res["pedidos_hoy"] == 3              # creados "ahora" → hoy
    assert res["ingresos_pagados"] == 1500.0    # solo los pagados
    assert res["items_vendidos"] == 5
    assert res["por_estado"] == {"pagado": 2, "pendiente_de_pago": 1}
    assert res["en_revision_fraude"] == 2
    assert len(res["recientes"]) == 3
    assert res["recientes"][0]["items"] == 3


def test_contar_en_revision_distinct(monkeypatch):
    # Cuenta pedidos marcados DISTINTOS (ignora repetidos y los sin pedido_id).
    payload = [{"pedido_id": "a"}, {"pedido_id": "b"}, {"pedido_id": "a"}, {"pedido_id": None}]
    monkeypatch.setattr(main.httpx, "AsyncClient", _client_con(200, payload))
    assert asyncio.run(main._contar_pedidos_en_revision()) == 2


def test_contar_en_revision_best_effort(monkeypatch):
    # Ante cualquier fallo de Anomalías → 0 (no rompe el resumen).
    class Boom:
        def __init__(self, **k): pass
        async def get(self, url): raise main.httpx.ConnectError("anomalias caído")
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **k: Boom())
    assert asyncio.run(main._contar_pedidos_en_revision()) == 0
