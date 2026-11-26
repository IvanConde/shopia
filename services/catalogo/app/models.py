import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import settings
from .database import Base

SCHEMA = settings.db_schema


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)

    productos: Mapped[list["Producto"]] = relationship(back_populates="categoria")


class Producto(Base):
    __tablename__ = "producto"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    precio: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    # FK real: la categoría vive en el mismo servicio/esquema.
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.categoria.id"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    categoria: Mapped["Categoria"] = relationship(back_populates="productos")
