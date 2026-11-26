"""Caché de plantillas en Redis (mejor esfuerzo).

Guarda las plantillas de notificación que genera el LLM, indexadas por arquetipo
de evento (estado + rango de monto), para no re-invocar al modelo ante eventos
similares. Si Redis no está disponible, se degrada silenciosamente (se genera sin
caché) para no romper el flujo de notificación.
"""

import logging

import redis.asyncio as redis

from .config import settings

logger = logging.getLogger("notificaciones.cache")

_cliente: redis.Redis | None = None


def _get_cliente() -> redis.Redis:
    global _cliente
    if _cliente is None:
        _cliente = redis.from_url(settings.redis_url, decode_responses=True)
    return _cliente


async def obtener(clave: str) -> str | None:
    try:
        return await _get_cliente().get(clave)
    except Exception as exc:  # noqa: BLE001 - degradación intencional
        logger.warning("Redis no disponible al leer %s: %s", clave, exc)
        return None


async def guardar(clave: str, valor: str) -> None:
    try:
        await _get_cliente().set(clave, valor, ex=settings.cache_ttl_s)
    except Exception as exc:  # noqa: BLE001 - degradación intencional
        logger.warning("Redis no disponible al escribir %s: %s", clave, exc)


async def cerrar() -> None:
    global _cliente
    if _cliente is not None:
        await _cliente.aclose()
        _cliente = None
