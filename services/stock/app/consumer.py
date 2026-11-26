"""Consumidor de Stock: cierra el ciclo de reserva.

  - `pedidos.creados`   -> **reserva** unidades (disponible-, reservado+); si no
                           alcanza, publica `stock.sin_stock` (extensión 4a).
  - `pagos.completados` -> **confirma** la reserva (reservado-; las unidades salen).
  - `pagos.rechazados`  -> **libera** la reserva (reservado-, disponible+; 3a: no
                           se descuenta stock).

Se procesa con prefetch=1 para preservar el orden (la reserva del pedido debe
existir antes de confirmarla/liberarla al llegar el resultado del pago).
"""

import asyncio
import json
import logging
from uuid import UUID

import aio_pika
from sqlalchemy import select

from . import models
from .config import settings
from .database import SessionLocal

logger = logging.getLogger("stock.consumer")

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None

_REINTENTOS_CONEXION = 10
_ESPERA_REINTENTO_S = 3.0


async def _conectar() -> aio_pika.abc.AbstractRobustConnection:
    for intento in range(1, _REINTENTOS_CONEXION + 1):
        try:
            return await aio_pika.connect_robust(settings.amqp_url)
        except (ConnectionError, aio_pika.exceptions.AMQPError) as exc:
            if intento == _REINTENTOS_CONEXION:
                raise
            logger.warning(
                "RabbitMQ no disponible (intento %s/%s): %s — reintento en %ss",
                intento, _REINTENTOS_CONEXION, exc, _ESPERA_REINTENTO_S,
            )
            await asyncio.sleep(_ESPERA_REINTENTO_S)


async def _publicar(routing_key: str, payload: dict) -> None:
    assert _exchange is not None
    mensaje = aio_pika.Message(
        body=json.dumps(payload, default=str).encode(),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await _exchange.publish(mensaje, routing_key=routing_key)


async def _reservar(evento: dict) -> None:
    pedido_id = UUID(evento["pedido_id"])
    async with SessionLocal() as session:
        for item in evento.get("items", []):
            producto_id = UUID(item["producto_id"])
            cantidad = int(item["cantidad"])
            stock = await session.get(models.Stock, producto_id)
            if stock is None or stock.disponible < cantidad:
                disponible = stock.disponible if stock else 0
                logger.warning(
                    "Sin stock pedido=%s producto=%s pide=%s disponible=%s",
                    pedido_id, producto_id, cantidad, disponible,
                )
                await _publicar(
                    "stock.sin_stock",
                    {"pedido_id": str(pedido_id), "producto_id": str(producto_id),
                     "solicitado": cantidad, "disponible": disponible},
                )
                continue
            stock.disponible -= cantidad
            stock.reservado += cantidad
            session.add(models.Reserva(
                pedido_id=pedido_id, producto_id=producto_id, cantidad=cantidad, estado="reservada",
            ))
            logger.info(
                "Reservado pedido=%s producto=%s x%s (disponible=%s reservado=%s)",
                pedido_id, producto_id, cantidad, stock.disponible, stock.reservado,
            )
        await session.commit()


async def _resolver_reservas(pedido_id: UUID, confirmar: bool) -> None:
    """Confirma (pago aprobado) o libera (pago rechazado) las reservas del pedido."""
    async with SessionLocal() as session:
        stmt = select(models.Reserva).where(
            models.Reserva.pedido_id == pedido_id, models.Reserva.estado == "reservada"
        )
        reservas = (await session.execute(stmt)).scalars().all()
        for reserva in reservas:
            stock = await session.get(models.Stock, reserva.producto_id)
            if stock is not None:
                stock.reservado -= reserva.cantidad
                if not confirmar:
                    stock.disponible += reserva.cantidad  # se devuelve al disponible
            reserva.estado = "confirmada" if confirmar else "liberada"
        await session.commit()
        if reservas:
            logger.info(
                "Reservas de pedido=%s %s (%s ítem/s)",
                pedido_id, "confirmadas" if confirmar else "liberadas", len(reservas),
            )


async def _procesar(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        evento = json.loads(message.body)
        rk = message.routing_key
        if rk == "pedidos.creados":
            await _reservar(evento)
        elif rk == "pagos.completados":
            await _resolver_reservas(UUID(evento["pedido_id"]), confirmar=True)
        elif rk == "pagos.rechazados":
            await _resolver_reservas(UUID(evento["pedido_id"]), confirmar=False)


async def iniciar_consumidor() -> None:
    global _connection, _exchange
    _connection = await _conectar()
    channel = await _connection.channel()
    # prefetch=1: procesa en orden (reservar antes de confirmar/liberar).
    await channel.set_qos(prefetch_count=1)
    _exchange = await channel.declare_exchange(
        settings.events_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(settings.queue_stock, durable=True)
    for rk in ("pedidos.creados", "pagos.completados", "pagos.rechazados"):
        await queue.bind(_exchange, routing_key=rk)
    await queue.consume(_procesar)
    logger.info("Consumidor iniciado: cola '%s' <- [pedidos.creados, pagos.completados, pagos.rechazados]",
                settings.queue_stock)


async def detener_consumidor() -> None:
    global _connection, _exchange
    if _connection is not None:
        await _connection.close()
        _connection = None
        _exchange = None
