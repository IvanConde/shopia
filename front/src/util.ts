// Utilidades de presentación compartidas por las vistas.

/** Formatea un monto en pesos con separador de miles local (74999 -> "$74.999"). */
export function precio(monto: number): string {
  return "$" + Math.round(monto).toLocaleString("es-AR");
}

/** Id corto para mostrar (los UUID completos son ruido visual). */
export function idCorto(id: string): string {
  return id.slice(0, 8);
}

export interface EstadoVisual {
  etiqueta: string;
  clase: string; // sufijo para .estado-badge--<clase>
}

// Mapea el estado del pedido a una etiqueta legible + un color (no se depende
// solo del color: siempre hay texto — WCAG "no usar solo color").
const ESTADOS: Record<string, EstadoVisual> = {
  creado: { etiqueta: "En proceso", clase: "neutro" },
  pagado: { etiqueta: "Pagado", clase: "ok" },
  pendiente_de_pago: { etiqueta: "Pendiente de pago", clase: "warn" },
  cancelado: { etiqueta: "Cancelado", clase: "danger" },
};

export function estadoVisual(estado: string): EstadoVisual {
  return ESTADOS[estado] ?? { etiqueta: estado, clase: "neutro" };
}

/** Gradiente pastel estable a partir de un id, como placeholder de imagen de
 *  producto (el catálogo del prototipo no almacena fotos). Mismo id → mismo
 *  gradiente, para que la "imagen" sea consistente entre pantallas. */
export function gradiente(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const a = h % 360;
  const b = (a + 45) % 360;
  return `linear-gradient(135deg, hsl(${a} 68% 88%), hsl(${b} 70% 80%))`;
}

/** Tiempo relativo legible a partir de un ISO ("recién", "hace 3 min", …). */
export function haceTiempo(iso: string | null): string {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "recién";
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  return new Date(iso).toLocaleDateString("es-AR");
}

/** Cómo se generó una notificación → etiqueta + clase de color (trazabilidad). */
export function backendNotif(b: string): { etiqueta: string; clase: string } {
  if (b === "gemini") return { etiqueta: "IA · Gemini", clase: "ia" };
  if (b === "cache") return { etiqueta: "IA · caché", clase: "cache" };
  return { etiqueta: "Respaldo", clase: "fallback" };
}

/** Oferta de DEMO estable por producto para el "modo evento" (CyberMonday).
 *  El precio real del catálogo es el precio con descuento (lo que efectivamente
 *  se cobra: total del checkout = total del backend). Esta función solo deriva,
 *  de forma estable por id, un "precio regular" de referencia MAYOR —un dato de
 *  ejemplo, rotulado en el banner— y el % de descuento mostrado. No altera ningún
 *  total real. Mismo id → misma oferta entre pantallas. */
export function ofertaDemo(seed: string, precioReal: number): { pct: number; lista: number } {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const pct0 = 15 + (h % 31); // 15–45 %
  const bruto = precioReal / (1 - pct0 / 100);
  let lista = Math.round(bruto / 1000) * 1000 - 1; // terminación comercial "…999"
  if (lista <= precioReal) lista = precioReal + 999;
  const pct = Math.round((1 - precioReal / lista) * 100); // coherente con el precio tachado
  return { pct, lista };
}

// Mapa nombre de producto → archivo de imagen (en public/img/). Se clavea por
// nombre porque los id de catálogo son UUID generados en la siembra (no estables).
const IMAGENES: Record<string, string> = {
  "Auriculares Aura Pro": "aura-pro",
  "Auriculares Aura Lite": "aura-lite",
  "Parlante Aura Boom": "aura-boom",
  "Teclado mecánico Nova K": "nova-k",
  "Mouse Nova M": "nova-m",
  "Monitor Nova View 27": "nova-view",
  "Cámara web Nova Cam HD": "nova-cam",
  "Smartwatch Pulse S": "pulse-s",
  "Banda deportiva Pulse Band": "pulse-band",
  "Notebook Nova Book 14": "nova-book",
  "Tablet Pulse Tab 11": "pulse-tab",
  "Smartphone Pulse Phone X": "pulse-phone-x",
  "Smartphone Pulse Phone Lite": "pulse-phone-lite",
  "Auriculares gamer Aura GX": "aura-gx",
  "Joystick inalámbrico Nova Pad": "nova-pad",
  "Parlante inteligente Aura Home": "aura-home",
};

/** Ruta de la foto del producto, o null si no hay (entonces se usa `gradiente`). */
export function imagenProducto(nombre: string): string | null {
  const slug = IMAGENES[nombre];
  return slug ? `/img/${slug}.jpg` : null;
}

/** Badge de stock a partir de las unidades disponibles (null = sin dato). */
export function stockVisual(disp: number | null): { etiqueta: string; clase: string } {
  if (disp == null) return { etiqueta: "Stock s/d", clase: "na" };
  if (disp === 0) return { etiqueta: "Sin stock", clase: "sin" };
  if (disp <= 5) return { etiqueta: `Últimas ${disp}`, clase: "pocas" };
  return { etiqueta: "En stock", clase: "ok" };
}
