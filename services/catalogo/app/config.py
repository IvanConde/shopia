from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Conexión a PostgreSQL (driver asíncrono asyncpg).
    database_url: str = "postgresql+asyncpg://pfi:pfi@postgres:5432/pfi"
    # Esquema propio del servicio (patrón base-de-datos-por-servicio).
    db_schema: str = "catalogo"


settings = Settings()
