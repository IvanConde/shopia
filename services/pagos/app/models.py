import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .config import settings
from .database import Base

SCHEMA = settings.db_schema


class Pago(Base):
    """Tabla PAGO. Registro del resultado de cada pago simulado.

    Las referencias a pedido/usuario son lógicas (viven en otros servicios). El
    pago se puntúa aguas arriba por el detector de anomalías; aquí solo se
    persiste el resultado del procesamiento.
    """

    __tablename__ = "pago"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    monto: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    medio: Mapped[str] = mapped_column(String(30), default="simulado", nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    procesado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
