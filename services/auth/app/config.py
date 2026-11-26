from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio, tomada del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Secreto compartido para firmar/validar el JWT (HS256). En dev proviene del compose.
    jwt_secret: str = "dev-secret-cambiar"
    jwt_alg: str = "HS256"
    jwt_expire_minutes: int = 120

    # Servicio de Usuarios: dueño de las credenciales. El login valida contra él
    # (además del usuario demo). Llamada interna por pfi_net (no por el gateway).
    usuarios_url: str = "http://usuarios:8000"
    http_timeout: float = 5.0


settings = Settings()

# Usuario de demostración, coherente con el ejemplo de los mockups (Juan Pérez).
USUARIOS_DEMO = {
    "juan@shopia.demo": {
        "password": "demo",
        "user_id": "11111111-1111-1111-1111-111111111111",
        "nombre": "Juan Pérez",
    },
}
