from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models, schemas
from .database import Base, engine, get_session
from .seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea las tablas del esquema del servicio (el esquema ya existe por el init SQL).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_if_empty()
    yield


app = FastAPI(title="Catálogo — ShopIA", version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "catalogo"}


@app.get("/categorias", response_model=list[schemas.CategoriaOut], tags=["catalogo"])
async def listar_categorias(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(models.Categoria).order_by(models.Categoria.nombre))
    return result.scalars().all()


@app.get("/productos", response_model=list[schemas.ProductoOut], tags=["catalogo"])
async def buscar_productos(
    q: str | None = Query(None, description="Texto libre para buscar por nombre o descripción."),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(models.Producto).where(models.Producto.activo.is_(True))
    if q:
        patron = f"%{q}%"
        stmt = stmt.where(
            or_(models.Producto.nombre.ilike(patron), models.Producto.descripcion.ilike(patron))
        )
    result = await session.execute(stmt.order_by(models.Producto.nombre))
    return result.scalars().all()


@app.get("/productos/{producto_id}", response_model=schemas.ProductoOut, tags=["catalogo"])
async def detalle_producto(producto_id: UUID, session: AsyncSession = Depends(get_session)):
    producto = await session.get(models.Producto, producto_id)
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto
