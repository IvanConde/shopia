"""Consumidor de resultados de pago: cierra el lazo del checkout.

Escucha en el mismo topic exchange los eventos que publica el servicio de Pagos
y actualiza el estado del pedido en consecuencia:
  - `pagos.completados` -> el pedido pasa a "pagado";
  - `pagos.rechazados`  -> el pedido queda "pendiente_de_pago" (extensión 3a).

Es la contraparte de `events.py` (que solo publica): aquí Pedidos actúa como
consumidor de eventos de dominio, cerrando el flujo asíncrono con Pagos.
"""

import asyncio
import json
import logging
from uuid import UUID

import aio_pika

from . import models
from .config import settings
from .database import SessionLocal

logger = logging.getLogger("pedidos.consumer")

_connection: aio_pika.abc.AbstractRobustConnection | None = None

# `connect_robust` solo reintenta tras la primera conexión exitosa; el arranque
# inicial puede pegarle a RabbitMQ antes de que acepte AMQP (aunque el
# healthcheck lo dé sano), así que se reintenta la primera conexión.
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

# Estado del pedido según el evento de pago recibido.
_ESTADO_POR_EVENTO = {
    "pagos.completados": "pagado",
    "pagos.rechazados": "pendiente_de_pago",
}


async def _procesar(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        nuevo_estado = _ESTADO_POR_EVENTO.get(message.routing_key)
        evento = json.loads(message.body)
        pedido_id = evento.get("pedido_id")
        if nuevo_estado is None or pedido_id is None:
            logger.warning("Evento de pago ignorado (rk=%s, payload=%s)", message.routing_key, evento)
            return

        async with SessionLocal() as session:
            pedido = await session.get(models.Pedido, UUID(pedido_id))
            if pedido is None:
                # Se descarta (ack) para no reencolar indefinidamente un id inexistente.
                logger.warning("Pago de pedido inexistente pedido=%s (rk=%s)", pedido_id, message.routing_key)
                return
            anterior = pedido.estado
            pedido.estado = nuevo_estado
            await session.commit()

        logger.info("Pedido %s: %s -> %s (por %s)", pedido_id, anterior, nuevo_estado, message.routing_key)


async def iniciar_consumidor() -> None:
    global _connection
    _connection = await _conectar()
    channel = await _connection.channel()
    await channel.set_qos(prefetch_count=10)
    exchange = await channel.declare_exchange(
        settings.events_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(settings.queue_pagos_resueltos, durable=True)
    for routing_key in _ESTADO_POR_EVENTO:
        await queue.bind(exchange, routing_key=routing_key)
    await queue.consume(_procesar)
    logger.info(
        "Consumidor iniciado: cola '%s' <- routing keys %s",
        settings.queue_pagos_resueltos,
        list(_ESTADO_POR_EVENTO),
    )


async def detener_consumidor() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
