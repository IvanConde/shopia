"""Cliente HTTP hacia el servicio de Catálogo (comunicación síncrona entre
servicios), protegido por un circuit breaker: si Catálogo está caído, el
error es inmediato (no se acumulan timeouts) una vez abierto el circuito."""

import logging
from uuid import UUID

import httpx

from .circuit_breaker import CircuitBreaker
from .config import settings

logger = logging.getLogger("pedidos.catalogo")

_breaker = CircuitBreaker(umbral_fallos=3, cooldown_s=15.0, nombre="catalogo")


class CatalogoNoDisponible(RuntimeError):
    """Catálogo no responde (o el circuito está abierto)."""


async def obtener_producto(producto_id: UUID) -> dict | None:
    """Devuelve el producto desde Catálogo, o None si no existe.

    Si el circuito está abierto, falla de inmediato con `CatalogoNoDisponible`;
    ante error de red cuenta el fallo (y puede abrir el circuito) y re-lanza.
    """
    if not _breaker.permite():
        raise CatalogoNoDisponible("Catálogo no disponible (circuito abierto).")
    try:
        async with httpx.AsyncClient(base_url=settings.catalogo_url, timeout=5.0) as client:
            respuesta = await client.get(f"/productos/{producto_id}")
        if respuesta.status_code == 404:
            _breaker.registrar_exito()  # respuesta válida: el servicio está sano
            return None
        respuesta.raise_for_status()
        _breaker.registrar_exito()
        return respuesta.json()
    except httpx.HTTPError as exc:
        _breaker.registrar_fallo()
        logger.warning("Catálogo falló (%s) [circuito=%s]", exc, _breaker.estado)
        raise CatalogoNoDisponible(str(exc)) from exc
