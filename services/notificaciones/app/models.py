import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .config import settings
from .database import Base

SCHEMA = settings.db_schema


class Notificacion(Base):
    """Notificación generada para un usuario (tabla NOTIFICACION).

    Las referencias a usuario/pedido son lógicas (viven en otros servicios). El
    campo `backend` deja trazable cómo se generó el texto: por el LLM, por caché
    de plantilla, o por la plantilla de respaldo.
    """

    __tablename__ = "notificacion"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    pedido_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    canal: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    asunto: Mapped[str] = mapped_column(String(160), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    evento: Mapped[str] = mapped_column(String(40), nullable=False)
    backend: Mapped[str] = mapped_column(String(40), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
