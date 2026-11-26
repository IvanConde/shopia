"""Publicación de eventos de dominio de Usuarios.

Publicación de "mejor esfuerzo": si el bus no está disponible, se registra y se
continúa, para no romper la operación sobre el perfil.
"""

import json
import logging

import aio_pika

from .config import settings

logger = logging.getLogger("usuarios.events")

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def _get_exchange() -> aio_pika.abc.AbstractExchange:
    global _connection, _exchange
    if _exchange is None:
        _connection = await aio_pika.connect_robust(settings.amqp_url)
        channel = await _connection.channel()
        _exchange = await channel.declare_exchange(
            settings.events_exchange, aio_pika.ExchangeType.TOPIC, durable=True
        )
    return _exchange


async def publicar_evento(routing_key: str, payload: dict) -> bool:
    try:
        exchange = await _get_exchange()
        mensaje = aio_pika.Message(
            body=json.dumps(payload, default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await exchange.publish(mensaje, routing_key=routing_key)
        logger.info("Evento publicado: %s", routing_key)
        return True
    except Exception as exc:  # noqa: BLE001 - degradación intencional
        logger.warning("No se pudo publicar el evento %s: %s", routing_key, exc)
        return False


async def cerrar_conexion() -> None:
    global _connection, _exchange
    if _connection is not None:
        await _connection.close()
        _connection = None
        _exchange = None
