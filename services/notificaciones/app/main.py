import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Query
from sqlalchemy import select

from . import models, redis_cache
from .config import settings
from .consumer import contadores, detener_consumidor, iniciar_consumidor
from .database import Base, SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await iniciar_consumidor()   # Escucha pagos.completados / pagos.rechazados.
    yield
    await detener_consumidor()
    await redis_cache.cerrar()


app = FastAPI(title="Notificaciones adaptativas — ShopIA", version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "notificaciones", "backend": settings.backend, **contadores()}


@app.get("/notificaciones", tags=["notificaciones"])
async def notificaciones(
    limit: int = Query(20, ge=1, le=100),
    audiencia: str = Query("cliente", description="cliente | operador"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    """Notificaciones generadas (más recientes primero).

    - `audiencia="cliente"` (por defecto): avisos al comprador (canal != interno);
      si viene `X-User-Id` (autenticado por el gateway), se filtran las del propio
      usuario.
    - `audiencia="operador"`: avisos internos del operador (p. ej. alertas de fraude),
      de todos los usuarios (vista de operador, demo-scoped — sin rol/RBAC real).
    """
    async with SessionLocal() as session:
        stmt = select(models.Notificacion).order_by(models.Notificacion.creado_en.desc())
        if audiencia == "operador":
            stmt = stmt.where(models.Notificacion.canal == "interno")
        else:
            stmt = stmt.where(models.Notificacion.canal != "interno")
            if x_user_id:
                try:
                    stmt = stmt.where(models.Notificacion.usuario_id == uuid.UUID(x_user_id))
                except ValueError:
                    pass  # X-User-Id inválido: no se filtra por usuario
        stmt = stmt.limit(limit)
        filas = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(n.id),
            "usuario_id": str(n.usuario_id) if n.usuario_id else None,
            "pedido_id": str(n.pedido_id) if n.pedido_id else None,
            "canal": n.canal,
            "asunto": n.asunto,
            "mensaje": n.mensaje,
            "evento": n.evento,
            "backend": n.backend,
            "creado_en": n.creado_en.isoformat() if n.creado_en else None,
        }
        for n in filas
    ]
