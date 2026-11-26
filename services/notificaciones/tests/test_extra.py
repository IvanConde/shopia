"""Pruebas del generador (camino completo), caché Redis, consumidor y endpoints
del motor de notificaciones. Se evita llamar al LLM y al bus reales con dobles.
Corre con asyncio.run (sin pytest-asyncio).
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app import consumer, generador, main, redis_cache


# --- Generador: camino completo (fallback y caché) --------------------------
def test_generar_usa_fallback_si_no_hay_llm(monkeypatch):
    monkeypatch.setattr(redis_cache, "obtener", AsyncMock(return_value=None))
    monkeypatch.setattr(generador, "_plantilla_llm", AsyncMock(return_value=None))
    datos = asyncio.run(generador.generar(
        "pagos.completados",
        {"pedido_id": "abcdef12-0000-0000-0000-000000000000", "usuario_id": "u1", "monto": 74999},
    ))
    assert datos["backend"] == "fallback"
    assert datos["asunto"] == "Confirmamos tu pago"
    assert "74.999" in datos["mensaje"] and "abcdef12" in datos["mensaje"]


def test_generar_rechazado_usa_plantilla_de_cache(monkeypatch):
    monkeypatch.setattr(
        redis_cache, "obtener",
        AsyncMock(return_value="Pago del {pedido} por ${monto} no pudo procesarse."),
    )
    datos = asyncio.run(generador.generar(
        "pagos.rechazados",
        {"pedido_id": "99999999-0000-0000-0000-000000000000", "usuario_id": "u2", "monto": 250000},
    ))
    assert datos["backend"] == "cache"
    assert datos["asunto"] == "Tuvimos un problema con tu pago"
    assert "250.000" in datos["mensaje"]


# --- Caché Redis ------------------------------------------------------------
def test_redis_roundtrip_y_degradacion(monkeypatch):
    store = {}

    class FakeClient:
        async def set(self, k, v, ex=None): store[k] = v
        async def get(self, k): return store.get(k)
    monkeypatch.setattr(redis_cache, "_get_cliente", lambda: FakeClient())
    asyncio.run(redis_cache.guardar("k", "v"))
    assert asyncio.run(redis_cache.obtener("k")) == "v"

    class Boom:
        async def set(self, k, v, ex=None): raise RuntimeError("redis caído")
        async def get(self, k): raise RuntimeError("redis caído")
    monkeypatch.setattr(redis_cache, "_get_cliente", lambda: Boom())
    assert asyncio.run(redis_cache.obtener("k")) is None
    asyncio.run(redis_cache.guardar("k", "v"))  # degrada sin romper


def test_a_texto_normaliza_contenido():
    assert generador._a_texto("hola") == "hola"
    assert generador._a_texto([{"text": "a"}, {"text": "b"}]) == "ab"
    assert generador._a_texto(None) == ""


def test_generar_creado_personaliza_por_segmento(monkeypatch):
    # pedidos.creados -> notificación "creado", con segmento/canal del perfil.
    monkeypatch.setattr(redis_cache, "obtener", AsyncMock(return_value=None))
    monkeypatch.setattr(generador, "_plantilla_llm", AsyncMock(return_value=None))
    datos = asyncio.run(generador.generar(
        "pedidos.creados",
        {"pedido_id": "abcdef12-0000-0000-0000-000000000000", "usuario_id": "u1", "total": 74999},
        perfil={"segmento": "recurrente", "canal_preferido": "sms"},
    ))
    assert datos["asunto"] == "Recibimos tu pedido"
    assert datos["canal"] == "sms" and datos["segmento"] == "recurrente"


def test_generar_fraude_va_al_operador(monkeypatch):
    # alertas.fraude -> notificación interna (operador), sin perfil de cliente.
    monkeypatch.setattr(redis_cache, "obtener", AsyncMock(return_value=None))
    monkeypatch.setattr(generador, "_plantilla_llm", AsyncMock(return_value=None))
    datos = asyncio.run(generador.generar(
        "alertas.fraude",
        {"pedido_id": "abcdef12-0000-0000-0000-000000000000", "usuario_id": "u1", "monto": 9_000_000},
    ))
    assert datos["canal"] == "interno" and datos["asunto"].startswith("Alerta")


def test_obtener_plantilla_gemini_cachea(monkeypatch):
    monkeypatch.setattr(redis_cache, "obtener", AsyncMock(return_value=None))
    monkeypatch.setattr(generador, "_plantilla_llm", AsyncMock(return_value="P {pedido} {monto}"))
    guardar = AsyncMock()
    monkeypatch.setattr(redis_cache, "guardar", guardar)
    plantilla, backend = asyncio.run(
        generador._obtener_plantilla("aprobado", "bajo", "recurrente", "email"))
    assert backend == "gemini" and "{pedido}" in plantilla
    guardar.assert_awaited()


def test_plantilla_llm_ok_y_falla(monkeypatch):
    import sys
    import types
    fake_mod = types.ModuleType("langchain_google_genai")

    class FakeLLM:
        def __init__(self, **k): pass
        async def ainvoke(self, msgs):
            return types.SimpleNamespace(content="Aviso para {pedido} por ${monto}.")
    fake_mod.ChatGoogleGenerativeAI = FakeLLM
    monkeypatch.setitem(sys.modules, "langchain_google_genai", fake_mod)
    assert "{pedido}" in asyncio.run(generador._plantilla_llm("aprobado", "bajo", "nuevo", "email"))

    class BoomLLM:
        def __init__(self, **k): pass
        async def ainvoke(self, msgs): raise RuntimeError("sin cuota")
    fake_mod.ChatGoogleGenerativeAI = BoomLLM
    assert asyncio.run(generador._plantilla_llm("aprobado", "bajo", "nuevo", "email")) is None


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


# --- Consumidor -------------------------------------------------------------
class _AProc:
    async def __aenter__(self): return None
    async def __aexit__(self, *a): return False


class FakeMessage:
    def __init__(self, body, rk="pagos.completados"):
        self.body = json.dumps(body).encode()
        self.routing_key = rk

    def process(self): return _AProc()


class FakeSession:
    def __init__(self): self.added = []
    def add(self, o): self.added.append(o)
    async def commit(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


def test_procesar_persiste_notificacion(monkeypatch):
    monkeypatch.setattr(consumer, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(consumer.usuarios_client, "obtener_perfil",
                        AsyncMock(return_value={"segmento": "recurrente", "canal_preferido": "email"}))
    monkeypatch.setattr(consumer.generador, "generar", AsyncMock(return_value={
        "usuario_id": "11111111-1111-1111-1111-111111111111",
        "pedido_id": "22222222-2222-2222-2222-222222222222",
        "canal": "email", "asunto": "A", "mensaje": "M",
        "evento": "pagos.completados", "backend": "fallback",
    }))
    asyncio.run(consumer._procesar(FakeMessage({"pedido_id": "x", "monto": 1})))
    assert "notificaciones_enviadas" in consumer.contadores()


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
def test_health_incluye_backend():
    r = asyncio.run(main.health())
    assert r["service"] == "notificaciones" and "backend" in r


def test_listar_notificaciones_vacio(monkeypatch):
    class Result:
        def scalars(self): return self
        def all(self): return []

    class S:
        async def execute(self, *a, **k): return Result()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    monkeypatch.setattr(main, "SessionLocal", lambda: S())
    # Nueva firma: audiencia + X-User-Id (llamada directa → se pasan explícitos,
    # porque fuera de FastAPI los default son los sentinels Query/Header).
    assert asyncio.run(main.notificaciones(limit=5, audiencia="cliente", x_user_id=None)) == []
