import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .consumer import detener_consumidor, iniciar_consumidor
from .database import Base, engine
from .store import listar_pagos, total_procesados

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await iniciar_consumidor()
    yield
    await detener_consumidor()


app = FastAPI(title="Pagos — ShopIA", version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "pagos", "pagos_procesados": await total_procesados()}


@app.get("/pagos", tags=["pagos"])
async def pagos():
    """Pagos simulados procesados desde el bus (más recientes primero)."""
    return await listar_pagos()
