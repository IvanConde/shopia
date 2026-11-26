from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio de Usuarios, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://pfi:pfi@postgres:5432/pfi"
    db_schema: str = "usuarios"

    # Bus de eventos (RabbitMQ / AMQP).
    amqp_url: str = "amqp://pfi:pfi@rabbitmq:5672/"
    events_exchange: str = "pfi.events"


settings = Settings()
