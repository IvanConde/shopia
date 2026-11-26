import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import settings
from .database import Base

SCHEMA = settings.db_schema


class Pedido(Base):
    __tablename__ = "pedido"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Referencia lógica al servicio Usuarios (sin FK que cruce el límite del servicio).
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    estado: Mapped[str] = mapped_column(String(40), default="creado", nullable=False)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    fecha_estimada: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Carga los ítems junto con el pedido (compatible con sesiones asíncronas).
    items: Mapped[list["ItemPedido"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", lazy="selectin"
    )


class ItemPedido(Base):
    __tablename__ = "item_pedido"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FK real: el ítem pertenece a un pedido del mismo servicio/esquema.
    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.pedido.id"), nullable=False)
    # Referencia lógica al servicio Catálogo.
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    pedido: Mapped["Pedido"] = relationship(back_populates="items")
