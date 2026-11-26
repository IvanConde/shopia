import type { Pedido } from "../types";
import { precio, idCorto, estadoVisual } from "../util";

interface Props {
  pedido: Pedido;
  nombres: Record<string, string>;
  anomalia: boolean;
  onVolver: () => void;
  onIrAlAsistente: () => void;
}

type PasoEstado = "done" | "current" | "failed" | "pending";
interface Paso { label: string; sub: string; estado: PasoEstado; }

function fecha(iso: string | null): string {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" }); }
  catch { return iso; }
}
function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("es-AR",
      { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

// La línea de progreso se arma desde el estado real del pedido (creado / pagado /
// pendiente_de_pago). "En preparación" y "Entregado" se muestran como etapas
// estimadas (el prototipo no modela despacho/entrega reales).
function pasosDe(p: Pedido): Paso[] {
  const entrega = fecha(p.fecha_estimada);
  const entregaSub = entrega !== "—" ? `Estimado ${entrega}` : "Estimado";
  if (p.estado === "pagado") {
    return [
      { label: "Pedido creado", sub: fechaHora(p.creado_en), estado: "done" },
      { label: "Pago aprobado", sub: "Confirmado", estado: "done" },
      { label: "En preparación", sub: "En curso", estado: "current" },
      { label: "Entregado", sub: entregaSub, estado: "pending" },
    ];
  }
  if (p.estado === "pendiente_de_pago") {
    return [
      { label: "Pedido creado", sub: fechaHora(p.creado_en), estado: "done" },
      { label: "Pago rechazado", sub: "Reintentá el pago", estado: "failed" },
      { label: "En preparación", sub: "—", estado: "pending" },
      { label: "Entregado", sub: "—", estado: "pending" },
    ];
  }
  return [
    { label: "Pedido creado", sub: fechaHora(p.creado_en), estado: "done" },
    { label: "Pago", sub: "Procesando…", estado: "current" },
    { label: "En preparación", sub: "—", estado: "pending" },
    { label: "Entregado", sub: entregaSub, estado: "pending" },
  ];
}

const ICONO: Record<PasoEstado, string> = { done: "✓", current: "●", failed: "✕", pending: "" };

export default function Seguimiento({ pedido, nombres, anomalia, onVolver, onIrAlAsistente }: Props) {
  const ev = estadoVisual(pedido.estado);
  const pasos = pasosDe(pedido);
  const cantidad = pedido.items.reduce((s, it) => s + it.cantidad, 0);

  return (
    <section className="seguimiento" aria-label={`Seguimiento del pedido ${idCorto(pedido.id)}`}>
      <nav className="migas" aria-label="Ruta de navegación">
        <button className="migas__link" onClick={onVolver}>Mis pedidos</button>
        <span className="migas__sep" aria-hidden="true">›</span>
        <span className="migas__actual" aria-current="page">Pedido #{idCorto(pedido.id)}</span>
      </nav>

      <div className="card-paso seg__cab">
        <div>
          <h1 className="seg__titulo">Pedido #{idCorto(pedido.id)}</h1>
          <p className="seg__meta">
            Realizado el {fecha(pedido.creado_en)} · {cantidad} {cantidad === 1 ? "producto" : "productos"} · {precio(pedido.total)}
          </p>
        </div>
        <div className="seg__estado">
          <span className="seg__estado-label">Estado actual</span>
          <span className={`estado-badge estado-badge--${ev.clase}`}>{ev.etiqueta}</span>
        </div>
      </div>

      {anomalia && (
        <div className="seg__anomalia" role="status">
          <span className="seg__anomalia-ico" aria-hidden="true">⚠️</span>
          <div>
            <p className="seg__anomalia-tit">Transacción marcada para revisión</p>
            <p className="seg__anomalia-txt">
              El detector de anomalías (Isolation Forest) señaló esta transacción como atípica.
              El pago se procesó, pero quedó en revisión antifraude.
            </p>
          </div>
        </div>
      )}

      <div className="card-paso">
        <ol className="stepper">
          {pasos.map((p, i) => (
            <li key={i} className={`stepper__paso stepper__paso--${p.estado}`}>
              <span className="stepper__circulo" aria-hidden="true">{ICONO[p.estado] || i + 1}</span>
              <span className="stepper__label">{p.label}</span>
              <span className="stepper__fecha">{p.sub}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="seg__grid">
        <div className="card-paso">
          <h2 className="card-paso__tit">Productos del pedido</h2>
          <ul className="items">
            {pedido.items.map((it, i) => (
              <li key={i} className="item">
                <span>{nombres[it.producto_id] ?? `Producto ${idCorto(it.producto_id)}`}</span>
                <span className="item__cant">× {it.cantidad}</span>
                <span className="item__precio">{precio(it.precio_unitario * it.cantidad)}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card-paso seg__asistente">
          <p className="detalle__asistente-tit">🤖 ¿Dudas con tu pedido?</p>
          <p className="detalle__asistente-txt">
            Preguntale al asistente por el estado, la fecha de entrega o cualquier cambio.
          </p>
          <button className="btn-secundario" onClick={onIrAlAsistente}>Abrir el asistente</button>
        </div>
      </div>
    </section>
  );
}
