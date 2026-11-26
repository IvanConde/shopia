from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Persistencia de la entidad PAGO (esquema propio en PostgreSQL).
    database_url: str = "postgresql+asyncpg://pfi:pfi@postgres:5432/pfi"
    db_schema: str = "pagos"

    amqp_url: str = "amqp://pfi:pfi@rabbitmq:5672/"
    events_exchange: str = "pfi.events"
    # Cola durable propia del servicio (sobrevive reinicios del broker).
    queue_pedidos_creados: str = "pagos.pedidos_creados"
    # Probabilidad de aprobación del pago simulado (~85 % aprobado).
    prob_aprobado: float = 0.85


settings = Settings()
