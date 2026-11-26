import { useState } from "react";
import { pagarCarrito } from "../api";
import type { CarritoItem, Pedido } from "../types";
import { precio, gradiente, ofertaDemo, imagenProducto } from "../util";

interface Props {
  carrito: CarritoItem[];
  evento?: boolean;
  onQuitar: (productoId: string) => void;
  onVolver: () => void;
  onIrABuscar: () => void;
  onPagado: (pedido: Pedido) => void;
}

type Metodo = "tarjeta" | "transferencia" | "efectivo";
type Modo = "aprobado" | "rechazado" | "anomalo";

const MODOS: { id: Modo; etiqueta: string }[] = [
  { id: "aprobado", etiqueta: "Aprobado" },
  { id: "rechazado", etiqueta: "Rechazado" },
  { id: "anomalo", etiqueta: "Anómalo" },
];

const AYUDA_MODO: Record<Modo, string> = {
  aprobado: "El pago simulado se aprueba (el pedido pasa a «pagado»).",
  rechazado: "El pago simulado se rechaza (el pedido queda «pendiente de pago»).",
  anomalo: "Inyecta una transacción atípica de prueba: el detector real de anomalías la marca.",
};

export default function Checkout({ carrito, evento, onQuitar, onVolver, onIrABuscar, onPagado }: Props) {
  const [metodo, setMetodo] = useState<Metodo>("tarjeta");
  const [modo, setModo] = useState<Modo>("aprobado");
  const [pagando, setPagando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const subtotal = carrito.reduce((s, c) => s + c.producto.precio * c.cantidad, 0);
  // Ahorro de demo del evento: diferencia contra el "precio regular" de ejemplo.
  // El total a pagar es siempre el precio real del catálogo (no cambia).
  const ahorro = evento
    ? carrito.reduce((s, c) => s + (ofertaDemo(c.producto.id, c.producto.precio).lista - c.producto.precio) * c.cantidad, 0)
    : 0;

  async function pagar() {
    setPagando(true);
    setError(null);
    try {
      const items = carrito.map((c) => ({ producto_id: c.producto.id, cantidad: c.cantidad }));
      const pedido = await pagarCarrito(items, modo);
      onPagado(pedido);
    } catch {
      setError("No se pudo procesar el pago. Reintentá en unos segundos.");
    } finally {
      setPagando(false);
    }
  }

  if (carrito.length === 0) {
    return (
      <section className="checkout" aria-label="Finalizar compra">
        <div className="vacio">
          <p className="vacio__titulo">Tu carrito está vacío</p>
          <p className="vacio__texto">Agregá productos para finalizar una compra.</p>
          <button className="btn-primario" onClick={onIrABuscar}>Ir a buscar productos</button>
        </div>
      </section>
    );
  }

  return (
    <section className="checkout" aria-label="Finalizar compra">
      <nav className="migas" aria-label="Ruta de navegación">
        <button className="migas__link" onClick={onVolver}>Catálogo</button>
        <span className="migas__sep" aria-hidden="true">›</span>
        <span className="migas__actual" aria-current="page">Finalizar compra</span>
      </nav>

      <h1 className="checkout__titulo">Finalizar compra</h1>

      <div className="checkout__grid">
        <div className="checkout__col">
          <div className="card-paso">
            <h2 className="card-paso__tit"><span className="paso-num">1</span> Resumen del pedido</h2>
            <ul className="resumen">
              {carrito.map((c) => {
                const img = imagenProducto(c.producto.nombre);
                return (
                <li key={c.producto.id} className="resumen__item">
                  <span className="resumen__img" style={img ? undefined : { background: gradiente(c.producto.id) }} aria-hidden="true">
                    {img && <img className="resumen__img-i" src={img} alt="" />}
                  </span>
                  <span className="resumen__info">
                    <span className="resumen__nombre">{c.producto.nombre}</span>
                    <span className="resumen__meta">Cantidad: {c.cantidad}</span>
                  </span>
                  <span className="resumen__precio">{precio(c.producto.precio * c.cantidad)}</span>
                  <button className="resumen__quitar" onClick={() => onQuitar(c.producto.id)}
                          aria-label={`Quitar ${c.producto.nombre}`}>✕</button>
                </li>
                );
              })}
            </ul>
          </div>

          <div className="card-paso">
            <h2 className="card-paso__tit"><span className="paso-num">2</span> Envío</h2>
            <p className="envio">
              <strong>Juan Pérez</strong><br />
              Av. Corrientes 1234, Piso 5 B<br />
              C1043 · CABA, Argentina<br />
              <span className="envio__eta">Entrega estimada: 3-5 días hábiles</span>
            </p>
            <p className="tag-ejemplo">dirección de ejemplo</p>
          </div>

          <div className="card-paso">
            <h2 className="card-paso__tit"><span className="paso-num">3</span> Método de pago</h2>
            <div className="metodos" role="group" aria-label="Método de pago">
              {(["tarjeta", "transferencia", "efectivo"] as Metodo[]).map((m) => (
                <button key={m}
                        className={`metodo ${metodo === m ? "metodo--activo" : ""}`}
                        aria-pressed={metodo === m}
                        onClick={() => setMetodo(m)}>
                  {m === "tarjeta" ? "💳 Tarjeta" : m === "transferencia" ? "Transferencia" : "Efectivo"}
                </button>
              ))}
            </div>
            {metodo === "tarjeta" && <p className="metodo__detalle">Visa •••• 4821 · Vence 08/29</p>}
          </div>
        </div>

        <aside className="checkout__pago">
          <h2 className="pago__tit">Total a pagar</h2>
          <dl className="pago__lineas">
            <div><dt>Subtotal</dt><dd>{precio(subtotal)}</dd></div>
            <div><dt>Envío</dt><dd>$0</dd></div>
            <div><dt>Impuestos</dt><dd>Incluidos</dd></div>
          </dl>
          <div className="pago__total"><span>Total</span><span>{precio(subtotal)}</span></div>
          {evento && ahorro > 0 && (
            <p className="pago__ahorro-nota">🔥 Ahorrás {precio(ahorro)} con CyberMonday</p>
          )}

          <div className="modo-demo">
            <p className="modo-demo__label">Modo demo (forzar resultado):</p>
            <div className="modo-demo__opciones" role="group" aria-label="Modo demo">
              {MODOS.map((m) => (
                <button key={m.id}
                        className={`modo-demo__btn modo-demo__btn--${m.id} ${modo === m.id ? "modo-demo__btn--activo" : ""}`}
                        aria-pressed={modo === m.id}
                        onClick={() => setModo(m.id)}>
                  {m.etiqueta}
                </button>
              ))}
            </div>
            <p className="modo-demo__ayuda">{AYUDA_MODO[modo]}</p>
          </div>

          {error && <p className="aviso-inline aviso-inline--error" role="alert">{error}</p>}

          <button className="btn-primario pago__btn" onClick={pagar} disabled={pagando}>
            {pagando ? "Procesando…" : "Pagar (simulado)"}
          </button>
        </aside>
      </div>
    </section>
  );
}
