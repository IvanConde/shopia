import { useEffect, useState } from "react";
import { alertasAnomalias, buscarProductos, historialPedidos } from "../api";
import Seguimiento from "./Seguimiento";
import type { Pedido } from "../types";
import { precio, idCorto, estadoVisual } from "../util";

type Estado = "cargando" | "listo" | "error";

const TOPE = 25; // se muestran los más recientes; el resto queda fuera por claridad

function fecha(iso: string | null): string {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" }); }
  catch { return iso; }
}

export default function MisPedidos(
  { refresco, nuevo, onIrABuscar, onIrAlAsistente }:
  { refresco: number; nuevo: Pedido | null; onIrABuscar: () => void; onIrAlAsistente: () => void }
) {
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [nombres, setNombres] = useState<Record<string, string>>({});
  const [alertados, setAlertados] = useState<Set<string>>(new Set());
  const [estado, setEstado] = useState<Estado>("cargando");
  const [detalle, setDetalle] = useState<Pedido | null>(null);

  async function cargar() {
    try {
      const [peds, prods, alertas] = await Promise.all([
        historialPedidos(),
        buscarProductos("").catch(() => []),
        alertasAnomalias(),
      ]);
      setPedidos(peds);
      setNombres(Object.fromEntries(prods.map((p) => [p.id, p.nombre])));
      setAlertados(new Set(alertas.map((a) => a.pedido_id).filter(Boolean) as string[]));
      setEstado("listo");
      // Si hay un pedido abierto en seguimiento, refrescamos su versión: así se ve
      // la transición de estado (creado → pagado / pendiente) sin salir de la vista.
      setDetalle((d) => (d ? (peds.find((p) => p.id === d.id) ?? d) : d));
    } catch {
      setEstado("error");
    }
  }

  useEffect(() => { cargar(); }, []);

  // Tras una compra (refresco cambia): se cae directo en el SEGUIMIENTO del pedido
  // recién hecho (para ver su código y estado, sin perderlo entre otros pedidos) y
  // se refresca un par de veces, para que la transición a "pagado"/"pendiente" (y
  // una posible alerta antifraude) sea visible dentro de esa misma vista.
  useEffect(() => {
    if (refresco === 0 || !nuevo) return;
    setPedidos((prev) => [nuevo, ...prev.filter((p) => p.id !== nuevo.id)]);
    setDetalle(nuevo);
    setEstado("listo");
    const t1 = window.setTimeout(() => { cargar(); }, 1400);
    const t2 = window.setTimeout(() => { cargar(); }, 3200);
    return () => { window.clearTimeout(t1); window.clearTimeout(t2); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresco]);

  // Vista de seguimiento de un pedido concreto.
  if (detalle) {
    return (
      <Seguimiento
        pedido={detalle}
        nombres={nombres}
        anomalia={alertados.has(detalle.id)}
        onVolver={() => setDetalle(null)}
        onIrAlAsistente={onIrAlAsistente}
      />
    );
  }

  return (
    <section className="pedidos" aria-label="Mis pedidos">
      <div className="pedidos__barra">
        <h2 className="pedidos__titulo">Mis pedidos</h2>
        <button className="btn-secundario" onClick={cargar} disabled={estado === "cargando"}>
          ↻ Actualizar
        </button>
      </div>

      {estado === "cargando" && (
        <div className="aviso" role="status"><span className="spinner" aria-hidden="true" /><p>Cargando tus pedidos…</p></div>
      )}

      {estado === "error" && (
        <div className="aviso aviso--error" role="alert">
          <p className="aviso__titulo">No pudimos cargar tus pedidos</p>
          <button className="btn-primario" onClick={cargar}>Reintentar</button>
        </div>
      )}

      {estado === "listo" && pedidos.length === 0 && (
        <div className="vacio">
          <p className="vacio__titulo">Todavía no tenés pedidos</p>
          <p className="vacio__texto">Cuando compres algo, acá vas a poder seguir su estado.</p>
          <button className="btn-primario" onClick={onIrABuscar}>Ir a buscar productos</button>
        </div>
      )}

      {estado === "listo" && pedidos.length > TOPE && (
        <p className="pedidos__conteo">Mostrando los {TOPE} más recientes de {pedidos.length}.</p>
      )}

      {estado === "listo" && pedidos.length > 0 && (
        <ul className="lista-pedidos">
          {pedidos.slice(0, TOPE).map((p) => {
            const ev = estadoVisual(p.estado);
            const marcado = alertados.has(p.id);
            return (
              <li key={p.id} className="pedido">
                <button
                  className="pedido__fila"
                  onClick={() => setDetalle(p)}
                  aria-label={`Ver seguimiento del pedido ${idCorto(p.id)}`}
                >
                  <span className="pedido__id">#{idCorto(p.id)}</span>
                  <span className={`estado-badge estado-badge--${ev.clase}`}>{ev.etiqueta}</span>
                  {marcado && <span className="estado-badge estado-badge--warn">⚠️ En revisión</span>}
                  <span className="pedido__total">{precio(p.total)}</span>
                  <span className="pedido__fecha">{fecha(p.creado_en)}</span>
                  <span className="pedido__chevron" aria-hidden="true">›</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
