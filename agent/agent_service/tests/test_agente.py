"""Pruebas del agente: planificador de respaldo determinista (ReAct), utilidades
de traza/normalización, carga de herramientas MCP (mockeada) y endpoints.
El backend Gemini real se valida por la suite E2E; acá se cubre su degradación.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app import agent, main, mcp_tools


# --- Herramienta MCP falsa --------------------------------------------------
class FakeTool:
    def __init__(self, name, payload):
        self.name = name
        self._payload = payload

    async def ainvoke(self, args):
        # Imita los adaptadores MCP: un bloque de contenido por elemento.
        return [{"type": "text", "text": json.dumps(item)} for item in self._payload]


def _tools():
    return {
        "buscar_productos": FakeTool("buscar_productos", [{"nombre": "Aura", "precio": 100}]),
        "consultar_estado_pedido": FakeTool("consultar_estado_pedido", [
            {"pedido_id": "22222222-2222-2222-2222-222222222222", "estado": "pagado",
             "total": 1000, "fecha_estimada": "2026-10-10"}]),
        "historial_pedidos": FakeTool("historial_pedidos", [
            {"estado": "pagado", "total": 1000}]),
    }


# --- Planificador de respaldo (las 3 intenciones) ---------------------------
def test_fallback_busca_productos(monkeypatch):
    monkeypatch.setattr(agent, "tools_por_nombre", AsyncMock(return_value=_tools()))
    r = asyncio.run(agent._responder_fallback("quiero auriculares aura"))
    assert r["backend"] == "fallback"
    assert "buscar_productos" in r["traza"][0]["accion"]
    assert "Aura" in r["respuesta"]


def test_fallback_consulta_estado(monkeypatch):
    monkeypatch.setattr(agent, "tools_por_nombre", AsyncMock(return_value=_tools()))
    r = asyncio.run(agent._responder_fallback(
        "en qué anda mi pedido 22222222-2222-2222-2222-222222222222"))
    assert "consultar_estado_pedido" in r["traza"][0]["accion"]
    assert "pagado" in r["respuesta"]


def test_fallback_historial(monkeypatch):
    monkeypatch.setattr(agent, "tools_por_nombre", AsyncMock(return_value=_tools()))
    r = asyncio.run(agent._responder_fallback(
        "mostrame mi historial del usuario 22222222-2222-2222-2222-222222222222"))
    assert "historial_pedidos" in r["traza"][0]["accion"]


def test_fallback_sin_herramientas(monkeypatch):
    monkeypatch.setattr(agent, "tools_por_nombre", AsyncMock(return_value={}))
    r = asyncio.run(agent._responder_fallback("hola"))
    assert "herramientas MCP" in r["respuesta"]


def test_redactar_maneja_errores():
    # consultar propaga el mensaje de error de la herramienta.
    assert agent._redactar("consultar_estado_pedido", [{"error": "no existe"}]) == "no existe"
    assert "No encontré" in agent._redactar("historial_pedidos", [{"error": "x"}])
    assert "No encontré" in agent._redactar("buscar_productos", [{"error": "x"}])


# --- Utilidades -------------------------------------------------------------
def test_a_texto():
    assert agent._a_texto("x") == "x"
    assert agent._a_texto([{"text": "a"}, {"text": "b"}]) == "ab"
    assert agent._a_texto(None) == ""


def test_parse_mcp_variantes():
    assert agent._parse_mcp([{"text": '{"a":1}'}]) == [{"a": 1}]
    assert agent._parse_mcp([{"a": 2}]) == [{"a": 2}]
    assert agent._parse_mcp("texto suelto") == [{"texto": "texto suelto"}]


def test_traza_desde_mensajes():
    class ToolMessage:
        def __init__(self, content): self.content = content
    ai = SimpleNamespace(content="pienso", tool_calls=[{"name": "t", "args": {"x": 1}}])
    traza = agent._traza_desde_mensajes([ai, ToolMessage("observación")])
    assert traza[0]["accion"].startswith("t(")
    assert traza[0]["observacion"] == "observación"


def test_limpiar_consulta():
    assert "auriculares" in agent._limpiar_consulta("quiero unos auriculares por favor")


# --- responder(): memoria/caché/traza + degradación Gemini → respaldo -------
def _mock_redis(monkeypatch, historial=None, cacheado=None):
    monkeypatch.setattr(agent.redis_store, "cargar_historial",
                        AsyncMock(return_value=historial or []))
    monkeypatch.setattr(agent.redis_store, "cache_obtener", AsyncMock(return_value=cacheado))
    monkeypatch.setattr(agent.redis_store, "cache_guardar", AsyncMock())
    monkeypatch.setattr(agent.redis_store, "guardar_turno", AsyncMock())
    monkeypatch.setattr(agent.redis_store, "registrar_traza", AsyncMock())


def test_responder_degrada_a_fallback(monkeypatch):
    # backend=="gemini" en el contenedor (hay clave); si el LLM falla, degrada.
    _mock_redis(monkeypatch)
    monkeypatch.setattr(agent, "_responder_gemini", AsyncMock(side_effect=RuntimeError("LLM caído")))
    monkeypatch.setattr(agent, "tools_por_nombre", AsyncMock(return_value=_tools()))
    r = asyncio.run(agent.responder("quiero auriculares aura"))
    assert r["backend"].startswith("fallback")


def test_responder_cache_hit_no_llama_al_modelo(monkeypatch):
    # primer turno con respuesta cacheada -> no se invoca el backend.
    _mock_redis(monkeypatch, cacheado={
        "backend": "gemini", "modelo": "x", "respuesta": "cacheada", "traza": []})
    nunca = AsyncMock()
    monkeypatch.setattr(agent, "_responder_core", nunca)
    r = asyncio.run(agent.responder("hola", usuario_id="u1"))
    assert r["respuesta"] == "cacheada" and "cache" in r["backend"]
    nunca.assert_not_awaited()


def test_responder_guarda_turno_y_traza(monkeypatch):
    _mock_redis(monkeypatch)
    monkeypatch.setattr(agent, "_responder_core", AsyncMock(return_value={
        "backend": "gemini", "modelo": "x", "respuesta": "ok", "traza": []}))
    asyncio.run(agent.responder("hola", usuario_id="u1", session_id="s1"))
    agent.redis_store.guardar_turno.assert_awaited()
    agent.redis_store.registrar_traza.assert_awaited()


def test_circuit_breaker_ciclo():
    from app.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(umbral_fallos=2, cooldown_s=60)
    assert cb.estado == "cerrado" and cb.permite()
    cb.registrar_fallo()
    assert cb.estado == "medio_abierto" and cb.permite()
    cb.registrar_fallo()
    assert cb.estado == "abierto" and not cb.permite()
    cb.registrar_exito()
    assert cb.estado == "cerrado" and cb.permite()


def test_responder_circuito_abierto_no_llama_gemini(monkeypatch):
    # tras N fallos del LLM, el circuito abre y se degrada sin intentarlo.
    _mock_redis(monkeypatch)
    agent._breaker_gemini.registrar_exito()  # parte cerrado
    monkeypatch.setattr(agent, "_responder_gemini", AsyncMock(side_effect=RuntimeError("sin cuota")))
    monkeypatch.setattr(agent, "tools_por_nombre", AsyncMock(return_value=_tools()))
    for _ in range(agent.settings.cb_umbral_fallos):
        asyncio.run(agent.responder("hola"))
    assert agent._breaker_gemini.estado == "abierto"
    agent._responder_gemini.reset_mock()
    r = asyncio.run(agent.responder("otra pregunta"))
    assert "circuito abierto" in r["backend"]
    agent._responder_gemini.assert_not_awaited()
    agent._breaker_gemini.registrar_exito()  # reset para no afectar otras pruebas


def test_redis_store_memoria_cache_traza(monkeypatch):
    from app import redis_store
    datos = {}

    class FakeCli:
        async def get(self, k): return datos.get(k)
        async def set(self, k, v, ex=None): datos[k] = v
        async def lpush(self, k, v): datos.setdefault(k, []).insert(0, v)
        async def ltrim(self, k, a, b): datos[k] = datos.get(k, [])[a:b + 1]
        async def lrange(self, k, a, b): return datos.get(k, [])[a:b + 1]
    monkeypatch.setattr(redis_store, "_get_cliente", lambda: FakeCli())
    asyncio.run(redis_store.guardar_turno("s1", "hola", "chau"))
    h = asyncio.run(redis_store.cargar_historial("s1"))
    assert ("user", "hola") in h and ("assistant", "chau") in h
    asyncio.run(redis_store.cache_guardar("u1", "preg", {"respuesta": "r"}))
    assert asyncio.run(redis_store.cache_obtener("u1", "preg"))["respuesta"] == "r"
    asyncio.run(redis_store.registrar_traza({"x": 1}))
    assert asyncio.run(redis_store.listar_trazas(5))[0]["x"] == 1


def test_listar_trazas_filtra_por_usuario(monkeypatch):
    # el registro es compartido; filtrar por usuario_id evita que un usuario
    # vea las trazas de otro. Sin usuario_id (operador) ve todo.
    from app import redis_store
    datos = {}

    class FakeCli:
        async def lpush(self, k, v): datos.setdefault(k, []).insert(0, v)
        async def ltrim(self, k, a, b): datos[k] = datos.get(k, [])[a:b + 1]
        async def lrange(self, k, a, b): return datos.get(k, [])[a:b + 1]
    monkeypatch.setattr(redis_store, "_get_cliente", lambda: FakeCli())
    asyncio.run(redis_store.registrar_traza({"usuario_id": "u1", "pregunta": "a"}))
    asyncio.run(redis_store.registrar_traza({"usuario_id": "u2", "pregunta": "b"}))
    asyncio.run(redis_store.registrar_traza({"usuario_id": "u1", "pregunta": "c"}))

    propias = asyncio.run(redis_store.listar_trazas(20, usuario_id="u1"))
    assert {t["usuario_id"] for t in propias} == {"u1"}
    assert {t["pregunta"] for t in propias} == {"a", "c"}
    # El endpoint hace fail-closed si no llega X-User-Id.
    assert asyncio.run(main.trazas(limit=20, x_user_id=None)) == []
    # Operador (sin filtro) ve todas.
    assert len(asyncio.run(redis_store.listar_trazas(20))) == 3


# --- Carga de herramientas MCP (mockeada) -----------------------------------
def test_cargar_tools_cachea(monkeypatch):
    mcp_tools._tools_por_usuario.clear()
    fake_client = SimpleNamespace(get_tools=AsyncMock(return_value=[FakeTool("buscar_productos", [])]))
    monkeypatch.setattr(mcp_tools, "MultiServerMCPClient", lambda cfg: fake_client)
    tools = asyncio.run(mcp_tools.cargar_tools())
    assert tools[0].name == "buscar_productos"
    porn = asyncio.run(mcp_tools.tools_por_nombre())
    assert "buscar_productos" in porn


def test_cargar_tools_con_usuario_manda_header(monkeypatch):
    # con usuario_id, la conexión al MCP incluye la cabecera X-User-Id.
    mcp_tools._tools_por_usuario.clear()
    capturado = {}

    def fake_ctor(cfg):
        capturado.update(cfg["pfi"])
        return SimpleNamespace(get_tools=AsyncMock(return_value=[FakeTool("x", [])]))
    monkeypatch.setattr(mcp_tools, "MultiServerMCPClient", fake_ctor)
    asyncio.run(mcp_tools.cargar_tools("11111111-1111-1111-1111-111111111111"))
    assert capturado["headers"]["X-User-Id"] == "11111111-1111-1111-1111-111111111111"


# --- Endpoints --------------------------------------------------------------
def test_health():
    assert asyncio.run(main.health())["service"] == "agente"


def test_chat(monkeypatch):
    monkeypatch.setattr(main, "responder", AsyncMock(return_value={
        "backend": "fallback", "modelo": "reglas", "respuesta": "ok", "traza": []}))
    out = asyncio.run(main.chat(main.ChatIn(mensaje="hola"), x_user_id=None))
    assert out["pregunta"] == "hola" and out["respuesta"] == "ok"


def test_chat_valida_longitud_del_mensaje():
    # Defensa en profundidad (prompt injection): el mensaje tiene tope de longitud
    # y no puede ir vacío.
    import pytest
    from pydantic import ValidationError
    main.ChatIn(mensaje="x" * 2000)  # el límite exacto se acepta
    with pytest.raises(ValidationError):
        main.ChatIn(mensaje="x" * 2001)
    with pytest.raises(ValidationError):
        main.ChatIn(mensaje="")
