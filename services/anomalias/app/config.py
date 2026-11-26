from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del detector de anomalías, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://pfi:pfi@postgres:5432/pfi"
    db_schema: str = "anomalias"

    # Bus de eventos (RabbitMQ / AMQP).
    amqp_url: str = "amqp://pfi:pfi@rabbitmq:5672/"
    events_exchange: str = "pfi.events"
    # Cola durable propia: transacciones a evaluar.
    queue_pagos_en_proceso: str = "anomalias.pagos_en_proceso"

    # Isolation Forest: proporción esperada de anomalías en el flujo (contamination).
    contaminacion: float = 0.02
    # Banco de transacciones REALES con que se ajusta el modelo desplegado
    # (ruta relativa al paquete `app`; ver datos/README.md para su procedencia).
    datos_entrenamiento: str = "datos/transacciones_reales.csv"
    # Tamaño de la muestra sintética de RESPALDO (solo si falta el banco real).
    muestra_entrenamiento: int = 3000
    # Semilla para reproducibilidad del entrenamiento.
    semilla: int = 42


settings = Settings()
