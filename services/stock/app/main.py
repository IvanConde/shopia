import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .consumer import detener_consumidor, iniciar_consumidor
from .database import Base, engine, get_session
from .seed import sembrar_stock

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await sembrar_stock()        # una fila de stock por producto del catálogo.
    await iniciar_consumidor()   # reserva/confirma/libera según eventos.
    yield
    await detener_consumidor()


app = FastAPI(title="Stock — ShopIA", version="0.1.0", lifespan=lifespan)


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    producto_id: UUID
    disponible: int
    reservado: int


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "stock"}


@app.get("/stock", response_model=list[StockOut], tags=["stock"])
async def listar(session: AsyncSession = Depends(get_session)):
    filas = (await session.execute(select(models.Stock))).scalars().all()
    return filas


@app.get("/stock/{producto_id}", response_model=StockOut, tags=["stock"])
async def obtener(producto_id: UUID, session: AsyncSession = Depends(get_session)):
    """Disponibilidad de un producto en tiempo real."""
    stock = await session.get(models.Stock, producto_id)
    if stock is None:
        raise HTTPException(status_code=404, detail="Producto sin registro de stock")
    return stock
