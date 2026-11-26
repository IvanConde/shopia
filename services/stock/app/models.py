import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .config import settings
from .database import Base

SCHEMA = settings.db_schema


class Stock(Base):
    """Tabla STOCK: una fila por producto.

    `producto_id` es la PK y a la vez una referencia lógica a Catálogo (sin FK que
    cruce el límite del servicio). Sin depósitos/ubicaciones (fuera de alcance).
    """

    __tablename__ = "stock"
    __table_args__ = {"schema": SCHEMA}

    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    disponible: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reservado: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Reserva(Base):
    """Reserva de stock por ítem de pedido (interna del servicio).

    Permite cerrar el ciclo: se reserva al crear el pedido, y luego se
    **confirma** (pago aprobado) o se **libera** (pago rechazado), sabiendo qué
    unidades corresponden a cada pedido (los eventos de pago no traen los ítems).
    """

    __tablename__ = "reserva"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    # reservada | confirmada | liberada
    estado: Mapped[str] = mapped_column(String(20), default="reservada", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
