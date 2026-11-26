// Contratos que devuelve el backend (ver agent y services).

export interface PasoTraza {
  paso: number;
  pensamiento: string;
  accion: string;
  observacion: string | null;
}

export interface RespuestaChat {
  pregunta: string;
  backend: string;
  modelo: string;
  respuesta: string;
  traza: PasoTraza[];
}

export interface Producto {
  id: string;
  nombre: string;
  descripcion?: string;
  precio: number;
  categoria_id?: string;
}

export interface Categoria {
  id: string;
  nombre: string;
}

export interface Stock {
  producto_id: string;
  disponible: number;
  reservado: number;
}

export interface ItemPedido {
  producto_id: string;
  cantidad: number;
  precio_unitario: number;
}

export interface Pedido {
  id: string;
  usuario_id: string;
  estado: string;
  total: number;
  fecha_estimada: string | null;
  creado_en: string;
  items: ItemPedido[];
}

export interface CarritoItem {
  producto: Producto;
  cantidad: number;
}

export interface Alerta {
  alerta_id: string;
  pago_id: string;
  pedido_id: string | null;
  usuario_id: string | null;
  monto: number;
  score: number;
  creado_en: string | null;
}

export interface PedidoResumen {
  pedido_id: string;
  estado: string;
  total: number;
  items: number;
  creado_en: string | null;
}

export interface ResumenVendedor {
  pedidos_total: number;
  pedidos_hoy: number;
  ingresos_pagados: number;
  items_vendidos: number;
  por_estado: Record<string, number>;
  en_revision_fraude: number;
  recientes: PedidoResumen[];
}

export interface Notificacion {
  id: string;
  usuario_id: string | null;
  pedido_id: string | null;
  canal: string;
  asunto: string;
  mensaje: string;
  evento: string;
  backend: string;
  creado_en: string | null;
}

export type Rol = "usuario" | "asistente";

export interface Mensaje {
  rol: Rol;
  texto: string;
}
