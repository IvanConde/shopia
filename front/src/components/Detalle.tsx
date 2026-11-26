import { useEffect, useRef, useState } from "react";
import { consultarStock } from "../api";
import type { Producto } from "../types";
import { precio, gradiente, stockVisual, ofertaDemo, imagenProducto } from "../util";

interface Props {
  producto: Producto;
  evento?: boolean;
  onVolver: () => void;
  onComprarAhora: (producto: Producto, cantidad: number) => void;
  onAgregar: (producto: Producto, cantidad: number) => void;
  onIrAlAsistente: () => void;
}

// Deriva "viñetas" de características a partir de la descripción real del
// producto (el catálogo guarda una descripción, no specs estructuradas).
function bullets(desc?: string): string[] {
  if (!desc) return [];
  return desc.split(/[.;]\s+/).map((s) => s.replace(/\.$/, "").trim()).filter(Boolean);
}

export default function Detalle({ producto, evento, onVolver, onComprarAhora, onAgregar, onIrAlAsistente }: Props) {
  const [stock, setStock] = useState<number | null>(null);
  const [cantidad, setCantidad] = useState(1);
  const [aviso, setAviso] = useState<string | null>(null);
  const [miniatura, setMiniatura] = useState(0);
  const avisoTimer = useRef<number | null>(null);

  useEffect(() => {
    let vivo = true;
    consultarStock(producto.id)
      .then((s) => { if (vivo) setStock(s?.disponible ?? null); })
      .catch(() => { if (vivo) setStock(null); });
    return () => { vivo = false; };
  }, [producto.id]);

  useEffect(() => () => { if (avisoTimer.current) window.clearTimeout(avisoTimer.current); }, []);

  const sv = stockVisual(stock);
  const sinStock = stock === 0;
  const tope = stock && stock > 0 ? stock : 99;
  const grad = gradiente(producto.id);
  const of = evento ? ofertaDemo(producto.id, producto.precio) : null;
  const img = imagenProducto(producto.nombre);

  function agregar() {
    onAgregar(producto, cantidad);
    setAviso(`✓ Agregado al carrito (${cantidad}).`);
    if (avisoTimer.current) window.clearTimeout(avisoTimer.current);
    avisoTimer.current = window.setTimeout(() => setAviso(null), 4000);
  }

  const caracteristicas = bullets(producto.descripcion);

  return (
    <section className="detalle" aria-label={`Detalle de ${producto.nombre}`}>
      <nav className="migas" aria-label="Ruta de navegación">
        <button className="migas__link" onClick={onVolver}>Inicio</button>
        <span className="migas__sep" aria-hidden="true">›</span>
        <button className="migas__link" onClick={onVolver}>Catálogo</button>
        <span className="migas__sep" aria-hidden="true">›</span>
        <span className="migas__actual" aria-current="page">{producto.nombre}</span>
      </nav>

      <div className="detalle__grid">
        <div className="detalle__galeria">
          {img ? (
            <img className="detalle__imagen" src={img} alt={producto.nombre} />
          ) : (
            <div className="detalle__imagen" style={{ background: grad }} role="img"
                 aria-label={producto.nombre} />
          )}
          <div className="detalle__miniaturas">
            {[0, 1, 2, 3].map((i) => (
              <button
                key={i}
                className={`miniatura ${miniatura === i ? "miniatura--activa" : ""}`}
                style={img ? undefined : { background: grad, filter: `hue-rotate(${i * 12}deg)` }}
                aria-label={`Vista ${i + 1}`}
                aria-pressed={miniatura === i}
                onClick={() => setMiniatura(i)}
              >
                {img && <img className="miniatura__img" src={img} alt="" />}
              </button>
            ))}
          </div>
        </div>

        <div className="detalle__info">
          <p className="detalle__eyebrow">Catálogo · ShopIA</p>
          <h1 className="detalle__nombre">{producto.nombre}</h1>

          <p className="detalle__rating">
            <span className="estrellas" aria-hidden="true">★★★★★</span>
            <span className="detalle__nota">4,8</span>
            <span className="detalle__opiniones">· 312 opiniones</span>
            <span className="tag-ejemplo">datos de ejemplo</span>
          </p>

          <div className="detalle__precio">
            {of && (
              <span className="detalle__precio-lista">
                <span className="precio-lista precio-lista--lg">{precio(of.lista)}</span>
                <span className="precio-off precio-off--lg">-{of.pct}%</span>
                <span className="tag-ejemplo">precio regular de ejemplo</span>
              </span>
            )}
            <span className="detalle__precio-ahora">{precio(producto.precio)}</span>
            {of && <span className="detalle__precio-evento">Precio CyberMonday</span>}
          </div>

          <div className="detalle__stock">
            <span className={`stock-badge stock-badge--${sv.clase}`}>
              {stock != null && stock > 0 ? `✓ En stock · ${stock} unidades` : sv.etiqueta}
            </span>
            <span className="badge badge--live">Disponibilidad en tiempo real</span>
          </div>

          {caracteristicas.length > 0 && (
            <ul className="detalle__specs">
              {caracteristicas.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          )}

          <div className="detalle__compra">
            <div className="cantidad" role="group" aria-label="Cantidad">
              <button className="cantidad__btn" onClick={() => setCantidad((n) => Math.max(1, n - 1))}
                      disabled={cantidad <= 1} aria-label="Quitar uno">−</button>
              <span className="cantidad__valor" aria-live="polite">{cantidad}</span>
              <button className="cantidad__btn" onClick={() => setCantidad((n) => Math.min(tope, n + 1))}
                      disabled={cantidad >= tope} aria-label="Agregar uno">+</button>
            </div>
            <button className="btn-primario detalle__comprar" onClick={() => onComprarAhora(producto, cantidad)}
                    disabled={sinStock}>
              {sinStock ? "Sin stock" : "Comprar ahora"}
            </button>
            <button className="btn-secundario detalle__agregar" onClick={agregar} disabled={sinStock}>
              Agregar al carrito
            </button>
          </div>

          {aviso && <p className="aviso-inline aviso-inline--ok" role="status">{aviso}</p>}

          <div className="detalle__asistente">
            <p className="detalle__asistente-tit">🤖 ¿Dudas sobre este producto?</p>
            <p className="detalle__asistente-txt">
              Preguntale al asistente por el stock, el estado de un pedido o para comparar
              opciones. Razona con datos reales.
            </p>
            <button className="btn-secundario" onClick={onIrAlAsistente}>Abrir el asistente</button>
          </div>
        </div>
      </div>
    </section>
  );
}
