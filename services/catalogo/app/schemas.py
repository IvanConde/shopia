import uuid

from pydantic import BaseModel, ConfigDict


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    descripcion: str
    precio: float
    categoria_id: uuid.UUID
    activo: bool
