import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .config import settings
from .database import Base

SCHEMA = settings.db_schema


class Usuario(Base):
    """Tabla USUARIO. Dueña del perfil del comprador.

    `segmento` es un atributo de personalización (el motor de
    notificaciones recupera el segmento del usuario). El `hash_password` guarda
    la contraseña hasheada con **bcrypt** (salt aleatorio por contraseña, nunca en
    claro); la verificación es por `checkpw` (ver `main._verificar`).
    """

    __tablename__ = "usuario"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    hash_password: Mapped[str] = mapped_column(String(128), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), default="comprador", nullable=False)
    segmento: Mapped[str] = mapped_column(String(30), default="nuevo", nullable=False)
    # Canal preferido de notificación: el motor de notificaciones
    # adapta el canal al perfil. Valores: email, sms, push, whatsapp.
    canal_preferido: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
