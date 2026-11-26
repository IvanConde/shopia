import logging
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from .config import USUARIOS_DEMO, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("auth")

app = FastAPI(title="Auth — ShopIA", version="0.1.0")


class LoginIn(BaseModel):
    email: str
    password: str


async def _verificar_en_usuarios(email: str, password: str) -> dict | None:
    """Valida las credenciales contra el servicio de Usuarios (dueño de las
    credenciales). Devuelve los datos del usuario o None (inválidas / servicio
    no disponible)."""
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.post(
                f"{settings.usuarios_url}/usuarios/verificar",
                json={"email": email, "password": password},
            )
        if resp.status_code == 200:
            return resp.json()
        return None
    except httpx.HTTPError as exc:
        log.warning("No se pudo validar contra Usuarios: %s", exc)
        return None


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "auth"}


@app.post("/login", tags=["auth"])
async def login(body: LoginIn):
    """Emite un JWT firmado (HS256) para un usuario válido.

    Valida primero contra el usuario demo (para que la demo funcione aunque
    Usuarios esté caído) y, si no coincide, contra el servicio de Usuarios, que
    es el dueño de las credenciales (incluye los usuarios registrados).
    """
    email = body.email.lower()
    demo = USUARIOS_DEMO.get(email)
    if demo is not None and demo["password"] == body.password:
        datos = {"user_id": demo["user_id"], "nombre": demo["nombre"]}
    else:
        datos = await _verificar_en_usuarios(email, body.password)
        if datos is None:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": datos["user_id"],
        "email": email,
        "nombre": datos["nombre"],
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
    }


@app.get("/verify", tags=["auth"])
async def verify(response: Response, authorization: str | None = Header(default=None)):
    """Punto de validación para el ForwardAuth de Traefik.

    Valida la firma del token; ante éxito responde 200 y expone el identificador
    del usuario en la cabecera `X-User-Id`, que el gateway propaga al servicio.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta el token Bearer")

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    response.headers["X-User-Id"] = str(payload.get("sub", ""))
    response.headers["X-User-Email"] = str(payload.get("email", ""))
    return {"ok": True}
