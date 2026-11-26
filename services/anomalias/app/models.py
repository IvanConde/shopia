import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .config import settings
from .database import Base

SCHEMA = settings.db_schema


class AlertaFraude(Base):
    """Alerta de transacción sospechosa (tabla ALERTA_FRAUDE).

    Se persiste solo cuando el detector marca la transacción como anómala; las
    referencias a pago/pedido/usuario son lógicas (viven en otros servicios).
    """

    __tablename__ = "alerta_fraude"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pago_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    monto: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    # Score del Isolation Forest: cuanto más negativo, más anómala la transacción.
    score: Mapped[float] = mapped_column(Float, nullable=False)
    es_anomalia: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
