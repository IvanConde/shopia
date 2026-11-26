import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemPedidoIn(BaseModel):
    producto_id: uuid.UUID
    cantidad: int = Field(gt=0, description="Cantidad solicitada (mayor a cero).")


class PedidoCreate(BaseModel):
    usuario_id: uuid.UUID
    items: list[ItemPedidoIn] = Field(min_length=1)
    # Solo para la demo: fuerza el resultado del pago simulado en vez del azar
    # ('aprobado' | 'rechazado' | 'anomalo'). Viaja en el evento del pedido hasta
    # Pagos; en un entorno real este campo se ignoraría.
    demo_forzar: str | None = Field(default=None)


class ItemPedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    producto_id: uuid.UUID
    cantidad: int
    precio_unitario: float


class PedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    estado: str
    total: float
    creado_en: datetime
    actualizado_en: datetime
    fecha_estimada: date | None
    items: list[ItemPedidoOut]
