from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://pfi:pfi@postgres:5432/pfi"
    db_schema: str = "pedidos"

    # Bus de eventos (RabbitMQ / AMQP).
    amqp_url: str = "amqp://pfi:pfi@rabbitmq:5672/"
    events_exchange: str = "pfi.events"
    # Cola durable propia: resultados del pago que cierran el lazo del pedido
    # (consume pagos.completados / pagos.rechazados).
    queue_pagos_resueltos: str = "pedidos.pagos_resueltos"

    # Servicio de Catálogo (llamada síncrona por nombre de red).
    catalogo_url: str = "http://catalogo:8000"
    # Servicio de Anomalías (para el conteo de pedidos en revisión en la vista de vendedor).
    anomalias_url: str = "http://anomalias:8000"


settings = Settings()
