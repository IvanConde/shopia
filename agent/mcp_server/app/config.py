from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servidor MCP, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Servicios de dominio a los que el servidor MCP hace de fachada. En la red
    # interna se llegan por nombre de servicio (no pasan por el gateway: la
    # comunicación servicio-a-servicio es de confianza dentro de pfi_net).
    catalogo_url: str = "http://catalogo:8000"
    pedidos_url: str = "http://pedidos:8000"
    stock_url: str = "http://stock:8000"
    anomalias_url: str = "http://anomalias:8000"

    # Timeout de las llamadas HTTP a los servicios de dominio (segundos).
    http_timeout: float = 10.0


settings = Settings()
