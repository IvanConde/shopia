"""Siembra una fila de stock por producto, consultando el catálogo al arrancar.

Best-effort: si Catálogo no responde, se registra y se continúa (el stock se
podrá sembrar luego); no bloquea el arranque del servicio. Como ambos servicios
arrancan a la vez, se reintenta la consulta hasta que el catálogo esté poblado,
para no quedar con el stock vacío por una condición de carrera en el arranque.
"""

import asyncio
import logging
import uuid

import httpx

from . import models
from .config import settings
from .database import SessionLocal

logger = logging.getLogger("stock.seed")

# Reintentos de la consulta inicial al catálogo (arranque simultáneo de servicios).
_INTENTOS = 15
_ESPERA_SEG = 2


async def _traer_productos() -> list[dict]:
    """Consulta el catálogo reintentando hasta que responda con productos."""
    ultimo_error: Exception | None = None
    async with httpx.AsyncClient(timeout=10) as client:
        for intento in range(1, _INTENTOS + 1):
            try:
                resp = await client.get(f"{settings.catalogo_url}/productos")
                resp.raise_for_status()
                productos = resp.json()
                if productos:
                    return productos
                logger.info(
                    "Catálogo aún sin productos (intento %s/%s); reintentando…",
                    intento,
                    _INTENTOS,
                )
            except Exception as exc:  # noqa: BLE001 - best effort, se reintenta
                ultimo_error = exc
                logger.info(
                    "Catálogo no disponible (intento %s/%s): %s",
                    intento,
                    _INTENTOS,
                    exc,
                )
            await asyncio.sleep(_ESPERA_SEG)
    if ultimo_error is not None:
        logger.warning("No se pudo sembrar stock desde Catálogo: %s", ultimo_error)
    else:
        logger.warning("Catálogo sin productos tras %s intentos; stock no sembrado.", _INTENTOS)
    return []


async def sembrar_stock() -> None:
    productos = await _traer_productos()
    if not productos:
        return

    creados = 0
    async with SessionLocal() as session:
        for p in productos:
            pid = uuid.UUID(p["id"])
            if await session.get(models.Stock, pid) is None:
                session.add(
                    models.Stock(producto_id=pid, disponible=settings.stock_inicial, reservado=0)
                )
                creados += 1
        await session.commit()
    logger.info("Stock sembrado: %s producto(s) nuevos (inicial=%s)", creados, settings.stock_inicial)
