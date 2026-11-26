"""Persistencia de los pagos procesados en el esquema `pagos` de PostgreSQL.

Reemplaza al registro en memoria anterior: la entidad PAGO ahora
se guarda de verdad en la base, por servicio (patrón database-per-service).
"""

from uuid import UUID

from sqlalchemy import func, select

from . import models
from .database import SessionLocal


def _uuid(valor) -> UUID | None:
    return UUID(valor) if valor else None


async def registrar_pago(pago: dict) -> None:
    """Persiste el resultado de un pago simulado."""
    async with SessionLocal() as session:
        session.add(
            models.Pago(
                id=_uuid(pago.get("pago_id")),
                pedido_id=_uuid(pago.get("pedido_id")),
                usuario_id=_uuid(pago.get("usuario_id")),
                monto=pago.get("monto") or 0,
                medio=pago.get("medio", "simulado"),
                estado=pago.get("estado", "desconocido"),
            )
        )
        await session.commit()


async def listar_pagos(limit: int = 50) -> list[dict]:
    """Pagos procesados (más recientes primero)."""
    async with SessionLocal() as session:
        stmt = (
            select(models.Pago)
            .order_by(models.Pago.procesado_en.desc())
            .limit(limit)
        )
        filas = (await session.execute(stmt)).scalars().all()
    return [
        {
            "pago_id": str(p.id),
            "pedido_id": str(p.pedido_id) if p.pedido_id else None,
            "usuario_id": str(p.usuario_id) if p.usuario_id else None,
            "monto": float(p.monto),
            "medio": p.medio,
            "estado": p.estado,
            "procesado_en": p.procesado_en.isoformat() if p.procesado_en else None,
        }
        for p in filas
    ]


async def total_procesados() -> int:
    async with SessionLocal() as session:
        return int((await session.execute(select(func.count(models.Pago.id)))).scalar_one())
