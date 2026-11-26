"""API del agente conversacional.

Expone un endpoint de chat que ejecuta el agente ReAct sobre las herramientas
MCP de dominio y devuelve, además de la respuesta, la traza de razonamiento
(pensamiento → acción → observación) para el panel de traza de la interfaz de chat.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Query
from pydantic import BaseModel, Field

from . import redis_store
from .agent import _breaker_gemini, responder
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await redis_store.cerrar()


app = FastAPI(title="Agente conversacional — ShopIA", version="0.1.0", lifespan=lifespan)


class ChatIn(BaseModel):
    # Tope de longitud del mensaje: acota el input del usuario (defensa en
    # profundidad ante prompt injection y evita prompts desmedidos que quemarían
    # cuota del LLM). La contención principal es el conjunto acotado de
    # herramientas MCP de solo lectura y la autorización por dueño: aun con
    # una inyección, el agente no puede leer datos ajenos ni escribir.
    mensaje: str = Field(..., min_length=1, max_length=2000,
                         description="Pregunta del comprador en lenguaje natural.")
    session_id: str | None = Field(
        default=None, description="Identificador de la conversación (memoria). "
        "Si se omite, se usa el usuario autenticado."
    )


class PasoTraza(BaseModel):
    paso: int
    pensamiento: str
    accion: str
    observacion: str | None = None


class ChatOut(BaseModel):
    pregunta: str
    backend: str
    modelo: str
    respuesta: str
    traza: list[PasoTraza]


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "agente", "backend": settings.backend,
            "circuito_gemini": _breaker_gemini.estado}


@app.post("/chat", response_model=ChatOut, tags=["agente"])
async def chat(body: ChatIn, x_user_id: str | None = Header(default=None, alias="X-User-Id")):
    # El gateway valida el JWT y propaga `X-User-Id`; el agente lo reenvía a las
    # herramientas MCP para que las consultas respeten al dueño y lo usa como
    # sesión de memoria si no se pasa `session_id`.
    resultado = await responder(body.mensaje, usuario_id=x_user_id, session_id=body.session_id)
    return {"pregunta": body.mensaje, **resultado}


@app.get("/trazas", tags=["agente"])
async def trazas(limit: int = Query(20, ge=1, le=50),
                 x_user_id: str | None = Header(default=None, alias="X-User-Id")):
    """Registro auditable de las trazas ReAct del propio usuario.

    El gateway valida el JWT y propaga `X-User-Id`; se filtra por ese identificador
    para que cada comprador vea solo sus interacciones y nunca las de otros.
    Si no llega el encabezado (no debería por el router protegido),
    se devuelve vacío en vez de exponer el registro completo (fail-closed)."""
    if x_user_id is None:
        return []
    return await redis_store.listar_trazas(limit, usuario_id=x_user_id)
