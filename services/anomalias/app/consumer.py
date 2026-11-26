"""Consumidor de `pagos.en_proceso`: evalúa cada transacción y, si es anómala,
persiste una alerta y publica `alertas.fraude` en el bus.

Sigue el patrón de base de datos por servicio: la alerta se guarda en el esquema
`anomalias`; la notificación al administrador la resolverá quien consuma
`alertas.fraude`.
"""

import asyncio
import json
import logging
from uuid import UUID

import aio_pika

from . import detector, models
from .config import settings
from .database import SessionLocal

logger = logging.getLogger("anomalias.consumer")

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None

# Contadores en memoria (para inspección en /health y en la demo).
_evaluadas = 0
_anomalias = 0

# `connect_robust` solo reintenta tras la primera conexión exitosa; el arranque
# puede pegarle a RabbitMQ antes de que acepte AMQP, así que se reintenta.
_REINTENTOS_CONEXION = 10
_ESPERA_REINTENTO_S = 3.0


def contadores() -> dict:
    return {"evaluadas": _evaluadas, "anomalias": _anomalias}


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


async def _procesar(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    global _evaluadas, _anomalias
    async with message.process():
        evento = json.loads(message.body)
        pago_id = evento.get("pago_id")
        monto = evento.get("monto")
        if pago_id is None or monto is None:
            logger.warning("Evento sin pago_id/monto, ignorado: %s", evento)
            return

        cantidad_items = evento.get("cantidad_items", 1)
        hora = evento.get("hora")
        es_anomalia, score = detector.evaluar(monto, cantidad_items, hora)
        _evaluadas += 1
        logger.info(
            "Transacción evaluada pago=%s monto=$%s items=%s hora=%s -> %s (score=%.4f)",
            pago_id, monto, cantidad_items, hora, "ANÓMALA" if es_anomalia else "normal", score,
        )
        if not es_anomalia:
            return # patrón normal: no se persiste ni se alerta (diseño).

        _anomalias += 1
        alerta = models.AlertaFraude(
            pago_id=UUID(pago_id),
            pedido_id=UUID(evento["pedido_id"]) if evento.get("pedido_id") else None,
            usuario_id=UUID(evento["usuario_id"]) if evento.get("usuario_id") else None,
            monto=monto,
            score=score,
            es_anomalia=True,
        )
        async with SessionLocal() as session:
            session.add(alerta)
            await session.commit()
            alerta_id = str(alerta.id)

        await _publicar(
            "alertas.fraude",
            {
                "alerta_id": alerta_id,
                "pago_id": pago_id,
                "pedido_id": evento.get("pedido_id"),
                "usuario_id": evento.get("usuario_id"),
                "monto": monto,
                "score": score,
            },
        )
        logger.warning("Alerta de fraude publicada alerta=%s pago=%s monto=$%s", alerta_id, pago_id, monto)


async def iniciar_consumidor() -> None:
    global _connection, _exchange
    _connection = await _conectar()
    channel = await _connection.channel()
    await channel.set_qos(prefetch_count=10)
    _exchange = await channel.declare_exchange(
        settings.events_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(settings.queue_pagos_en_proceso, durable=True)
    await queue.bind(_exchange, routing_key="pagos.en_proceso")
    await queue.consume(_procesar)
    logger.info(
        "Consumidor iniciado: cola '%s' <- routing key 'pagos.en_proceso'",
        settings.queue_pagos_en_proceso,
    )


async def detener_consumidor() -> None:
    global _connection, _exchange
    if _connection is not None:
        await _connection.close()
        _connection = None
        _exchange = None
