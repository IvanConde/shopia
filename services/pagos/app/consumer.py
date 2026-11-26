"""Consumidor de `pedidos.creados` y simulador de pago (paso 3).

Flujo: consume el evento del pedido, simula el resultado del pago y
publica los eventos de dominio `pagos.en_proceso` y luego
`pagos.completados` / `pagos.rechazados` en el mismo topic exchange.
"""

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

import aio_pika

from .config import settings
from .store import registrar_pago

logger = logging.getLogger("pagos.consumer")

# Zona horaria de Argentina (UTC-3, sin horario de verano desde 2009). Se usa un
# offset fijo para no depender del paquete `tzdata` en la imagen. La hora local es
# la que importa para el detector de anomalías, que aprende la franja horaria local
# de compra; publicarla en UTC desplazaba las compras de la tarde-noche a la
# "madrugada" y disparaba falsos positivos.
_TZ_AR = timezone(timedelta(hours=-3))

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None

# `connect_robust` solo reintenta tras la primera conexión exitosa; el arranque
# en frío puede pegarle a RabbitMQ antes de que acepte AMQP (aunque el
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


async def _publicar(routing_key: str, payload: dict) -> None:
    assert _exchange is not None
    mensaje = aio_pika.Message(
        body=json.dumps(payload, default=str).encode(),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await _exchange.publish(mensaje, routing_key=routing_key)


async def _procesar(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        evento = json.loads(message.body)
        pedido_id = evento.get("pedido_id")
        usuario_id = evento.get("usuario_id")
        monto = evento.get("total", 0)
        # Señales para el detector de anomalías: cantidad de ítems del
        # pedido y hora de procesamiento.
        cantidad_items = sum(it.get("cantidad", 0) for it in evento.get("items", [])) or 1
        hora = datetime.now(_TZ_AR).hour # hora local: coincide con la franja que entrena el detector

        # Resultado del pago: aleatorio (prob_aprobado) salvo que la demo lo fuerce.
        # `demo_forzar` solo llega desde la UI de demostración; en uso real es None.
        demo = evento.get("demo_forzar")
        if demo == "aprobado":
            aprobado = True
        elif demo == "rechazado":
            aprobado = False
        elif demo == "anomalo":
            aprobado = True  # el pago se aprueba; abajo se inyecta el patrón atípico
        else:
            aprobado = random.random() < settings.prob_aprobado
        estado = "completado" if aprobado else "rechazado"

        # Señales multivariadas para el detector (monto, ítems, hora). En modo demo
        # 'anomalo' se inyecta una transacción atípica de prueba —igual que el
        # benchmark—: el Isolation Forest real decide si la marca.
        if demo == "anomalo":
            monto_senal = max(float(monto) * 20, 5_000_000.0)
            items_senal = max(cantidad_items, 50)
            hora_senal = 3  # madrugada: fuera de la franja habitual de compra
        else:
            monto_senal, items_senal, hora_senal = monto, cantidad_items, hora
        pago = {
            "pago_id": str(uuid.uuid4()),
            "pedido_id": pedido_id,
            "usuario_id": usuario_id,
            "monto": monto,
            "medio": "simulado",
            "estado": estado,
            "procesado_en": datetime.now(timezone.utc).isoformat(),
        }
        await registrar_pago(pago)
        logger.info("Pago simulado pedido=%s -> %s ($%s)", pedido_id, estado, monto)

        # Evento previo (lo consumirá el detector de anomalías). Lleva las
        # señales multivariadas que usa el detector (monto, ítems, hora).
        await _publicar(
            "pagos.en_proceso",
            {"pago_id": pago["pago_id"], "pedido_id": pago["pedido_id"],
             "usuario_id": pago["usuario_id"], "medio": pago["medio"],
             "monto": monto_senal, "cantidad_items": items_senal, "hora": hora_senal,
             "estado": "en_proceso"},
        )
        # Resultado final del pago. Lleva usuario_id y monto para que los
        # consumidores (Pedidos cierra el lazo; Notificaciones arma el aviso)
        # tengan un contrato autosuficiente sin volver a consultar a otro servicio.
        routing_key = "pagos.completados" if aprobado else "pagos.rechazados"
        await _publicar(
            routing_key,
            {k: pago[k] for k in ("pago_id", "pedido_id", "usuario_id", "monto", "estado")},
        )


async def iniciar_consumidor() -> None:
    global _connection, _exchange
    _connection = await _conectar()
    channel = await _connection.channel()
    await channel.set_qos(prefetch_count=10)
    _exchange = await channel.declare_exchange(
        settings.events_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(settings.queue_pedidos_creados, durable=True)
    await queue.bind(_exchange, routing_key="pedidos.creados")
    await queue.consume(_procesar)
    logger.info("Consumidor iniciado: cola '%s' <- routing key 'pedidos.creados'",
                settings.queue_pedidos_creados)


async def detener_consumidor() -> None:
    global _connection, _exchange
    if _connection is not None:
        await _connection.close()
        _connection = None
        _exchange = None
