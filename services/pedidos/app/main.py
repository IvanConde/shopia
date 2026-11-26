import logging
from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models, schemas
from .catalogo_client import CatalogoNoDisponible, obtener_producto
from .config import settings
from .consumer import detener_consumidor, iniciar_consumidor
from .database import Base, engine, get_session
from .events import cerrar_conexion, publicar_evento

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Escucha los resultados de pago para cerrar el lazo del pedido.
    await iniciar_consumidor()
    yield
    await detener_consumidor()
    await cerrar_conexion()


app = FastAPI(title="Pedidos — ShopIA", version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "pedidos"}


@app.post("/pedidos", response_model=schemas.PedidoOut, status_code=201, tags=["pedidos"])
async def crear_pedido(body: schemas.PedidoCreate, session: AsyncSession = Depends(get_session)):
    # Se resuelve el precio de cada ítem consultando a Catálogo (fuente de verdad del precio).
    total = Decimal("0")
    items: list[models.ItemPedido] = []
    for item in body.items:
        try:
            producto = await obtener_producto(item.producto_id)
        except CatalogoNoDisponible:
            # Fail-fast: Catálogo no responde / circuito abierto.
            raise HTTPException(status_code=503, detail="Catálogo no disponible; reintentá más tarde")
        if producto is None:
            raise HTTPException(status_code=400, detail=f"Producto {item.producto_id} inexistente")
        precio = Decimal(str(producto["precio"]))
        total += precio * item.cantidad
        items.append(
            models.ItemPedido(
                producto_id=item.producto_id, cantidad=item.cantidad, precio_unitario=precio
            )
        )

    pedido = models.Pedido(
        usuario_id=body.usuario_id,
        estado="creado",
        total=total,
        fecha_estimada=date.today() + timedelta(days=5),
        items=items,
    )
    session.add(pedido)
    await session.commit()
    await session.refresh(pedido)

    # Evento de dominio: dispara notificaciones y detección de anomalías.
    await publicar_evento(
        "pedidos.creados",
        {
            "pedido_id": str(pedido.id),
            "usuario_id": str(pedido.usuario_id),
            "total": float(pedido.total),
            "estado": pedido.estado,
            "items": [
                {
                    "producto_id": str(it.producto_id),
                    "cantidad": it.cantidad,
                    "precio_unitario": float(it.precio_unitario),
                }
                for it in pedido.items
            ],
            "creado_en": pedido.creado_en,
            # Solo demo: se propaga al simulador de pago (Pagos) para forzar el
            # resultado. None en uso normal (pago aleatorio).
            "demo_forzar": body.demo_forzar,
        },
    )
    return pedido


async def _contar_pedidos_en_revision() -> int:
    """Cantidad de pedidos marcados por el detector de anomalías (scope global).

    Mejor esfuerzo: consulta a Anomalías SIN reenviar `X-User-Id` (vista de
    operador, ve todas las alertas); ante cualquier fallo devuelve 0 y no rompe
    el resumen."""
    try:
        async with httpx.AsyncClient(base_url=settings.anomalias_url, timeout=5.0) as client:
            resp = await client.get("/alertas")
        if resp.status_code != 200:
            return 0
        return len({a.get("pedido_id") for a in resp.json() if a.get("pedido_id")})
    except Exception:  # noqa: BLE001 - best effort
        return 0


@app.get("/vendedor/resumen", tags=["vendedor"])
async def resumen_vendedor(session: AsyncSession = Depends(get_session)):
    """Resumen de operación para la vista de vendedor (el pico
    golpea también al operador).

    Agrega sobre **todos** los pedidos (scope vendedor/operador), a diferencia del
    historial, que filtra por dueño. Es una vista de operador del prototipo:
    no hay rol/RBAC de vendedor real; en producción iría detrás de ese rol.
    """
    pedidos = (
        await session.execute(select(models.Pedido).order_by(models.Pedido.creado_en.desc()))
    ).scalars().all()

    hoy = date.today()
    por_estado: dict[str, int] = {}
    ingresos = Decimal("0")
    items_vendidos = 0
    pedidos_hoy = 0
    for p in pedidos:
        por_estado[p.estado] = por_estado.get(p.estado, 0) + 1
        if p.estado == "pagado":
            ingresos += p.total
        if p.creado_en and p.creado_en.date() == hoy:
            pedidos_hoy += 1
        items_vendidos += sum(it.cantidad for it in p.items)

    recientes = [
        {
            "pedido_id": str(p.id),
            "estado": p.estado,
            "total": float(p.total),
            "items": sum(it.cantidad for it in p.items),
            "creado_en": p.creado_en.isoformat() if p.creado_en else None,
        }
        for p in pedidos[:12]
    ]

    return {
        "pedidos_total": len(pedidos),
        "pedidos_hoy": pedidos_hoy,
        "ingresos_pagados": float(ingresos),
        "items_vendidos": items_vendidos,
        "por_estado": por_estado,
        "en_revision_fraude": await _contar_pedidos_en_revision(),
        "recientes": recientes,
    }


@app.get("/pedidos/{pedido_id}", response_model=schemas.PedidoOut, tags=["pedidos"])
async def consultar_pedido(
    pedido_id: UUID,
    session: AsyncSession = Depends(get_session),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    pedido = await session.get(models.Pedido, pedido_id)
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    # Autorización por dueño: el usuario autenticado solo accede a sus
    # propios pedidos. El gateway valida el JWT y propaga `X-User-Id`; si el
    # pedido pertenece a otro, se responde 404 (no 403) para no revelar su
    # existencia. Sin el header (llamada interna de confianza en pfi_net) no se
    # restringe, porque el único acceso externo es a través del gateway.
    if x_user_id and str(pedido.usuario_id) != x_user_id:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return pedido


@app.get("/pedidos", response_model=list[schemas.PedidoOut], tags=["pedidos"])
async def historial_pedidos(
    usuario_id: UUID | None = Query(
        default=None, description="Identificador del comprador. Uso interno."
    ),
    session: AsyncSession = Depends(get_session),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    # Autorización por dueño: si la petición viene autenticada por el
    # gateway, el dueño del JWT (`X-User-Id`) manda y no se puede listar el
    # historial de otro; el parámetro de consulta solo se usa en llamadas
    # internas (p. ej. la fachada MCP) donde no hay header.
    if x_user_id:
        try:
            efectivo = UUID(x_user_id)
        except ValueError:
            raise HTTPException(status_code=401, detail="Identidad de usuario inválida")
    elif usuario_id is not None:
        efectivo = usuario_id
    else:
        raise HTTPException(status_code=400, detail="Falta el identificador de usuario")

    stmt = (
        select(models.Pedido)
        .where(models.Pedido.usuario_id == efectivo)
        .order_by(models.Pedido.creado_en.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()
