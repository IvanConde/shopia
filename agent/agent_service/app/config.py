from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del agente conversacional, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Servidor MCP de dominio (transporte streamable-http).
    mcp_url: str = "http://mcp:8000/mcp"

    # Backend del modelo de lenguaje (free tier de Google Gemini). Si la clave
    # está vacía, el agente usa un planificador determinista de respaldo que
    # igualmente ejercita las herramientas MCP (útil para probar sin credenciales).
    gemini_api_key: str = ""
    modelo_gemini: str = "gemini-flash-lite-latest"

    # Redis: memoria conversacional (historial por sesión), caché de respuestas y
    # registro auditable de la traza ReAct. Degradación a sin-estado si
    # Redis no está disponible.
    redis_url: str = "redis://redis:6379/0"
    cache_ttl_s: int = 60          # respuestas a preguntas sueltas (primer turno)
    historial_max_turnos: int = 8  # turnos (pregunta+respuesta) que se recuerdan
    historial_ttl_s: int = 1800    # vida de la conversación en Redis (30 min)
    trazas_max: int = 50           # trazas ReAct retenidas para auditoría

    # Circuit breaker sobre el backend Gemini: tras N fallos seguidos se
    # corta por `cooldown` segundos y se responde directo con el respaldo.
    cb_umbral_fallos: int = 3
    cb_cooldown_s: float = 30.0

    @property
    def backend(self) -> str:
        return "gemini" if self.gemini_api_key.strip() else "fallback"


settings = Settings()
