"""Estado del agente en Redis (mejor esfuerzo): memoria conversacional por
sesión, caché de respuestas y registro auditable de la traza ReAct.

Si Redis no está disponible, todo degrada en silencio: el agente sigue
respondiendo (sin memoria ni caché) para no romper el chat.
"""

import json
import logging

import redis.asyncio as redis

from .config import settings

log = logging.getLogger("agente.redis")

_cliente: redis.Redis | None = None

_HIST = "agente:hist:{session}"
_CACHE = "agente:cache:{usuario}:{preg}"
_TRAZAS = "agente:trazas"


def _get_cliente() -> redis.Redis:
    global _cliente
    if _cliente is None:
        _cliente = redis.from_url(settings.redis_url, decode_responses=True)
    return _cliente


# --- Memoria conversacional -------------------------------------------------
async def cargar_historial(session_id: str | None) -> list[tuple[str, str]]:
    """Devuelve el historial [(rol, texto), ...] de la sesión (vacío si no hay)."""
    if not session_id:
        return []
    try:
        crudo = await _get_cliente().get(_HIST.format(session=session_id))
        if not crudo:
            return []
        return [(m["rol"], m["texto"]) for m in json.loads(crudo)]
    except Exception as exc:  # noqa: BLE001 - degradación intencional
        log.warning("Redis no disponible al leer historial %s: %s", session_id, exc)
        return []


async def guardar_turno(session_id: str | None, pregunta: str, respuesta: str) -> None:
    """Agrega el turno (usuario + asistente) al historial, recortado a los
    últimos N turnos."""
    if not session_id:
        return
    try:
        historial = await cargar_historial(session_id)
        historial.append(("user", pregunta))
        historial.append(("assistant", respuesta))
        historial = historial[-settings.historial_max_turnos * 2:]
        payload = json.dumps([{"rol": r, "texto": t} for r, t in historial], ensure_ascii=False)
        await _get_cliente().set(_HIST.format(session=session_id), payload,
                                 ex=settings.historial_ttl_s)
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis no disponible al guardar historial %s: %s", session_id, exc)


# --- Caché de respuestas (preguntas sueltas / primer turno) -----------------
async def cache_obtener(usuario_id: str | None, pregunta: str) -> dict | None:
    try:
        clave = _CACHE.format(usuario=usuario_id or "-", preg=_norm(pregunta))
        crudo = await _get_cliente().get(clave)
        return json.loads(crudo) if crudo else None
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis no disponible al leer caché: %s", exc)
        return None


async def cache_guardar(usuario_id: str | None, pregunta: str, resultado: dict) -> None:
    try:
        clave = _CACHE.format(usuario=usuario_id or "-", preg=_norm(pregunta))
        await _get_cliente().set(clave, json.dumps(resultado, ensure_ascii=False),
                                 ex=settings.cache_ttl_s)
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis no disponible al guardar caché: %s", exc)


def _norm(texto: str) -> str:
    return " ".join(texto.lower().split())[:200]


# --- Registro auditable de la traza ReAct ---------------------------
async def registrar_traza(entrada: dict) -> None:
    """Loguea la traza (auditable en los logs del servicio) y la retiene en una
    lista acotada en Redis para inspección."""
    log.info("TRAZA %s", json.dumps(entrada, ensure_ascii=False))
    try:
        cli = _get_cliente()
        await cli.lpush(_TRAZAS, json.dumps(entrada, ensure_ascii=False))
        await cli.ltrim(_TRAZAS, 0, settings.trazas_max - 1)
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis no disponible al registrar traza: %s", exc)


async def listar_trazas(limit: int = 20, usuario_id: str | None = None) -> list[dict]:
    """Devuelve las últimas trazas. El registro es una lista compartida, así que
    cuando se pasa `usuario_id` se filtra por dueño: cada usuario solo ve sus
    propias interacciones, nunca las de otros. Sin `usuario_id`
    (uso interno/operador) devuelve el registro completo."""
    try:
        # Se lee el registro completo acotado y luego se filtra/recorta: filtrar
        # sobre un `lrange(0, limit-1)` dejaría afuera trazas del propio usuario
        # si las últimas son de otros.
        crudo = await _get_cliente().lrange(_TRAZAS, 0, settings.trazas_max - 1)
        entradas = [json.loads(c) for c in crudo]
        if usuario_id is not None:
            entradas = [e for e in entradas if e.get("usuario_id") == usuario_id]
        return entradas[:limit]
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis no disponible al listar trazas: %s", exc)
        return []


async def cerrar() -> None:
    global _cliente
    if _cliente is not None:
        await _cliente.aclose()
        _cliente = None
