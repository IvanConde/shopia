"""Consumidor de resultados de pago: genera y persiste una notificación
adaptativa por cada `pagos.completados` / `pagos.rechazados`.
"""

import asyncio
import json
import logging
from uuid import UUID

import aio_pika

from . import generador, models, usuarios_client
from .config import settings
from .database import SessionLocal

logger = logging.getLogger("notificaciones.consumer")

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_enviadas = 0

# Eventos que disparan una notificación: creación del pedido, resultado del pago
# y alerta de fraude (esta última dirigida al operador).
_ROUTING_KEYS = ("pedidos.creados", "pagos.completados", "pagos.rechazados", "alertas.fraude")

# `connect_robust` solo reintenta tras la primera conexión exitosa; el arranque
# puede pegarle a RabbitMQ antes de que acepte AMQP, así que se reintenta.
_REINTENTOS_CONEXION = 10
_ESPERA_REINTENTO_S = 3.0


def contadores() -> dict:
    return {"notificaciones_enviadas": _enviadas}


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


async def _procesar(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    global _enviadas
    async with message.process():
        evento = json.loads(message.body)
        # Para avisos al cliente se consulta su perfil (segmento + canal) y se
        # adapta el mensaje; la alerta de fraude va al operador, sin perfil.
        perfil = None
        if message.routing_key != "alertas.fraude":
            perfil = await usuarios_client.obtener_perfil(evento.get("usuario_id"))
        datos = await generador.generar(message.routing_key, evento, perfil)

        notif = models.Notificacion(
            usuario_id=UUID(datos["usuario_id"]) if datos.get("usuario_id") else None,
            pedido_id=UUID(datos["pedido_id"]) if datos.get("pedido_id") else None,
            canal=datos["canal"],
            asunto=datos["asunto"],
            mensaje=datos["mensaje"],
            evento=datos["evento"],
            backend=datos["backend"],
        )
        async with SessionLocal() as session:
            session.add(notif)
            await session.commit()

        _enviadas += 1
        logger.info(
            "Notificación generada pedido=%s evento=%s backend=%s: %s",
            datos.get("pedido_id"), message.routing_key, datos["backend"], datos["mensaje"],
        )


async def iniciar_consumidor() -> None:
    global _connection
    _connection = await _conectar()
    channel = await _connection.channel()
    await channel.set_qos(prefetch_count=10)
    exchange = await channel.declare_exchange(
        settings.events_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(settings.queue_pagos_resueltos, durable=True)
    for routing_key in _ROUTING_KEYS:
        await queue.bind(exchange, routing_key=routing_key)
    await queue.consume(_procesar)
    logger.info(
        "Consumidor iniciado: cola '%s' <- routing keys %s",
        settings.queue_pagos_resueltos, list(_ROUTING_KEYS),
    )


async def detener_consumidor() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
