import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header
from sqlalchemy import select

from . import detector, models
from .consumer import contadores, detener_consumidor, iniciar_consumidor
from .database import Base, SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    detector.entrenar()          # Isolation Forest ajustado sobre transacciones reales (UCI Online Retail).
    await iniciar_consumidor()   # Escucha pagos.en_proceso.
    yield
    await detener_consumidor()


app = FastAPI(title="Detección de anomalías — ShopIA", version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "anomalias", **contadores()}


@app.get("/alertas", tags=["anomalias"])
async def alertas(x_user_id: str | None = Header(default=None, alias="X-User-Id")):
    """Alertas de fraude detectadas (más recientes primero).

    Si llega `X-User-Id` (lo propaga el gateway tras validar el JWT) se filtran por
    dueño: cada usuario solo ve las alertas de sus propias transacciones.
    Sin el encabezado (acceso interno/operador) se devuelven todas."""
    filtro_uid = None
    if x_user_id is not None:
        try:
            filtro_uid = uuid.UUID(x_user_id)
        except ValueError:
            return []  # identidad inválida -> fail-closed
    async with SessionLocal() as session:
        stmt = select(models.AlertaFraude).order_by(models.AlertaFraude.creado_en.desc())
        if filtro_uid is not None:
            stmt = stmt.where(models.AlertaFraude.usuario_id == filtro_uid)
        filas = (await session.execute(stmt)).scalars().all()
    return [
        {
            "alerta_id": str(a.id),
            "pago_id": str(a.pago_id),
            "pedido_id": str(a.pedido_id) if a.pedido_id else None,
            "usuario_id": str(a.usuario_id) if a.usuario_id else None,
            "monto": float(a.monto),
            "score": a.score,
            "creado_en": a.creado_en.isoformat() if a.creado_en else None,
        }
        for a in filas
    ]
