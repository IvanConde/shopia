// Capa de acceso a la API del prototipo, siempre a través del gateway (mismo
// origen). Las rutas /api/* las enruta Traefik; el front nunca habla con los
// servicios directamente.
import type { Alerta, Categoria, Notificacion, Pedido, Producto, RespuestaChat, ResumenVendedor, Stock } from "./types";

// Usuario de demostración (coincide con el sembrado en el servicio auth).
export const USUARIO_DEMO = {
  email: "juan@shopia.demo",
  password: "demo",
  id: "11111111-1111-1111-1111-111111111111",
};

let token: string | null = null;

// Identificador de conversación estable por pestaña del navegador: habilita la
// memoria conversacional del agente sin mezclar hilos entre sesiones.
export const SESSION_ID =
  (crypto?.randomUUID?.() ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`);

/** Inicia sesión con el usuario demo y cachea el JWT en memoria. */
export async function login(): Promise<void> {
  const r = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: USUARIO_DEMO.email,
      password: USUARIO_DEMO.password,
    }),
  });
  if (!r.ok) throw new Error(`Login falló (HTTP ${r.status})`);
  const data = await r.json();
  token = data.access_token;
}

function authHeaders(): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Busca productos en el catálogo (ruta pública). `q` vacío lista todos. */
export async function buscarProductos(q = ""): Promise<Producto[]> {
  const r = await fetch(`/api/catalogo/productos?q=${encodeURIComponent(q)}`);
  if (!r.ok) throw new Error(`Búsqueda falló (HTTP ${r.status})`);
  return r.json();
}

/** Lista las categorías del catálogo (ruta pública). */
export async function listarCategorias(): Promise<Categoria[]> {
  const r = await fetch("/api/catalogo/categorias");
  if (!r.ok) throw new Error(`Categorías falló (HTTP ${r.status})`);
  return r.json();
}

/** Disponibilidad de stock de un producto (ruta pública). */
export async function consultarStock(productoId: string): Promise<Stock | null> {
  const r = await fetch(`/api/stock/${productoId}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`Stock falló (HTTP ${r.status})`);
  return r.json();
}

/** Historial de pedidos del usuario autenticado (el gateway filtra por dueño). */
export async function historialPedidos(): Promise<Pedido[]> {
  const r = await fetch(`/api/pedidos?usuario_id=${USUARIO_DEMO.id}`, {
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error(`Historial falló (HTTP ${r.status})`);
  return r.json();
}

/** Detalle de un pedido por id. */
export async function obtenerPedido(id: string): Promise<Pedido> {
  const r = await fetch(`/api/pedidos/${id}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`Pedido falló (HTTP ${r.status})`);
  return r.json();
}

/** Crea un pedido (checkout) con un producto y cantidad. */
export async function crearPedido(productoId: string, cantidad = 1): Promise<Pedido> {
  const r = await fetch("/api/pedidos", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      usuario_id: USUARIO_DEMO.id,
      items: [{ producto_id: productoId, cantidad }],
    }),
  });
  if (!r.ok) throw new Error(`No se pudo crear el pedido (HTTP ${r.status})`);
  return r.json();
}

/** Crea un pedido (checkout) con varios ítems. `demoForzar` solo se usa en la
 *  demo para forzar el resultado del pago simulado (aprobado/rechazado/anomalo). */
export async function pagarCarrito(
  items: { producto_id: string; cantidad: number }[],
  demoForzar?: string | null,
): Promise<Pedido> {
  const r = await fetch("/api/pedidos", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      usuario_id: USUARIO_DEMO.id,
      items,
      ...(demoForzar ? { demo_forzar: demoForzar } : {}),
    }),
  });
  if (!r.ok) throw new Error(`No se pudo crear el pedido (HTTP ${r.status})`);
  return r.json();
}

/** Alertas del detector de anomalías del usuario autenticado (el gateway filtra
 *  por dueño con X-User-Id). Devuelve [] si el servicio no está disponible. */
export async function alertasAnomalias(): Promise<Alerta[]> {
  try {
    const r = await fetch("/api/anomalias/alertas", { headers: authHeaders() });
    if (!r.ok) return [];
    return await r.json();
  } catch {
    return [];
  }
}

/** Resumen de operación para la vista de vendedor (scope operador: agrega todos
 *  los pedidos). Requiere sesión (JWT). Demo: sin rol/RBAC de vendedor real. */
export async function resumenVendedor(): Promise<ResumenVendedor> {
  const r = await fetch("/api/vendedor/resumen", { headers: authHeaders() });
  if (!r.ok) throw new Error(`Resumen de vendedor falló (HTTP ${r.status})`);
  return r.json();
}

/** Notificaciones adaptativas del comprador autenticado (el gateway filtra por
 *  dueño). Devuelve [] si el servicio no está disponible. */
export async function listarNotificaciones(): Promise<Notificacion[]> {
  try {
    const r = await fetch("/api/notificaciones?audiencia=cliente", { headers: authHeaders() });
    if (!r.ok) return [];
    return await r.json();
  } catch {
    return [];
  }
}

/** Avisos internos para el operador (p. ej. alertas de fraude). Vista de operador. */
export async function avisosOperador(): Promise<Notificacion[]> {
  try {
    const r = await fetch("/api/notificaciones?audiencia=operador", { headers: authHeaders() });
    if (!r.ok) return [];
    return await r.json();
  } catch {
    return [];
  }
}

/** Envía un mensaje al agente conversacional y devuelve respuesta + traza. */
export async function preguntar(mensaje: string): Promise<RespuestaChat> {
  const r = await fetch("/api/agente/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ mensaje, session_id: SESSION_ID }),
  });
  if (!r.ok) throw new Error(`El agente respondió HTTP ${r.status}`);
  return r.json();
}
