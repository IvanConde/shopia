from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del motor de notificaciones, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://pfi:pfi@postgres:5432/pfi"
    db_schema: str = "notificaciones"

    # Bus de eventos (RabbitMQ / AMQP).
    amqp_url: str = "amqp://pfi:pfi@rabbitmq:5672/"
    events_exchange: str = "pfi.events"
    # Cola durable propia: eventos que disparan una notificación. Escucha
    # creación de pedido, resultados de pago y alertas de fraude.
    queue_pagos_resueltos: str = "notificaciones.pagos_resueltos"

    # Servicio de Usuarios: se consulta el perfil (segmento y canal preferido) para
    # adaptar el tono y el canal de la notificación. Llamada interna.
    usuarios_url: str = "http://usuarios:8000"
    http_timeout: float = 5.0

    # Caché de plantillas generadas por el LLM (Redis). Evita re-invocar al modelo
    # para el mismo arquetipo de evento (estado + rango de monto).
    redis_url: str = "redis://redis:6379/0"
    cache_ttl_s: int = 3600

    # Backend del texto (free tier de Google Gemini). Sin clave => plantilla
    # determinista de respaldo, con los mismos guardrails.
    gemini_api_key: str = ""
    modelo_gemini: str = "gemini-flash-lite-latest"

    @property
    def backend(self) -> str:
        return "gemini" if self.gemini_api_key.strip() else "fallback"


settings = Settings()
