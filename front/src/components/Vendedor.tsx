import { useEffect, useState } from "react";
import { resumenVendedor, avisosOperador } from "../api";
import type { ResumenVendedor, Notificacion } from "../types";
import { precio, idCorto, estadoVisual, haceTiempo, backendNotif } from "../util";

interface Props {
  evento: boolean;
  onToggleEvento: () => void;
  onVolver: () => void;
}

type Estado = "cargando" | "listo" | "error";

export default function Vendedor({ evento, onToggleEvento, onVolver }: Props) {
  const [data, setData] = useState<ResumenVendedor | null>(null);
  const [avisos, setAvisos] = useState<Notificacion[]>([]);
  const [estado, setEstado] = useState<Estado>("cargando");

  async function cargar() {
    setEstado("cargando");
    try {
      const [resumen, ops] = await Promise.all([resumenVendedor(), avisosOperador()]);
      setData(resumen);
      setAvisos(ops);
      setEstado("listo");
    } catch {
      setEstado("error");
    }
  }

  useEffect(() => { cargar(); }, []);

  const d = data;
  const enProc = d ? d.por_estado["creado"] ?? 0 : 0;
  const pend = d ? d.por_estado["pendiente_de_pago"] ?? 0 : 0;

  return (
    <section className="vendedor" aria-label="Panel de vendedor">
      <nav className="migas" aria-label="Ruta de navegación">
        <button className="migas__link" onClick={onVolver}>Inicio</button>
        <span className="migas__sep" aria-hidden="true">›</span>
        <span className="migas__actual" aria-current="page">Panel de vendedor</span>
      </nav>

      <div className="vendedor__head">
        <div>
          <h1 className="vendedor__tit">Panel de vendedor</h1>
          <p className="vendedor__sub">
            Operación de tu tienda en ShopIA
            <span className="tag-ejemplo">vista de operador (demo)</span>
          </p>
        </div>
        <button
          className={`btn-primario vendedor__campana ${evento ? "vendedor__campana--on" : ""}`}
          onClick={onToggleEvento}
        >
          {evento ? "🔥 CyberMonday activo · desactivar" : "🔥 Lanzar campaña CyberMonday"}
        </button>
      </div>

      {estado === "cargando" && (
        <div className="aviso" role="status"><span className="spinner" aria-hidden="true" /><p>Cargando la operación…</p></div>
      )}

      {estado === "error" && (
        <div className="aviso aviso--error" role="alert">
          <p className="aviso__titulo">No se pudo cargar el panel</p>
          <button className="btn-primario" onClick={cargar}>Reintentar</button>
        </div>
      )}

      {estado === "listo" && d && (
        <>
          <div className="kpis">
            <div className="kpi">
              <span className="kpi__lbl">Pedidos hoy</span>
              <span className="kpi__val">{d.pedidos_hoy}</span>
              <span className="kpi__sub">{d.pedidos_total} en total</span>
            </div>
            <div className="kpi">
              <span className="kpi__lbl">Ingresos (pagados)</span>
              <span className="kpi__val">{precio(d.ingresos_pagados)}</span>
              <span className="kpi__sub">{d.items_vendidos} ítems vendidos</span>
            </div>
            <div className="kpi">
              <span className="kpi__lbl">En proceso</span>
              <span className="kpi__val">{enProc}</span>
              <span className="kpi__sub">{pend} pendientes de pago</span>
            </div>
            <div className={`kpi ${d.en_revision_fraude > 0 ? "kpi--alerta" : ""}`}>
              <span className="kpi__lbl">En revisión por fraude</span>
              <span className="kpi__val">{d.en_revision_fraude}</span>
              <span className="kpi__sub">detector de anomalías</span>
            </div>
          </div>

          {avisos.length > 0 && (
            <>
              <h2 className="vendedor__seccion">Avisos al operador</h2>
              <ul className="avisos-op">
                {avisos.slice(0, 5).map((x) => {
                  const b = backendNotif(x.backend);
                  return (
                    <li key={x.id} className="aviso-op">
                      <span className="aviso-op__icono" aria-hidden="true">⚠️</span>
                      <div className="aviso-op__cuerpo">
                        <p className="aviso-op__asunto">{x.asunto}</p>
                        <p className="aviso-op__msg">{x.mensaje}</p>
                        <p className="notif__meta">
                          <span className={`notif__backend notif__backend--${b.clase}`}>{b.etiqueta}</span>
                          <span className="notif__hora">{haceTiempo(x.creado_en)}</span>
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </>
          )}

          <h2 className="vendedor__seccion">Pedidos recientes</h2>
          {d.recientes.length === 0 ? (
            <p className="vendedor__vacio">
              Todavía no hay pedidos. Generá una compra desde el catálogo para verla acá.
            </p>
          ) : (
            <div className="tabla-wrap">
              <table className="tabla-ped">
                <thead>
                  <tr><th>Pedido</th><th>Estado</th><th>Ítems</th><th>Total</th><th>Fecha</th></tr>
                </thead>
                <tbody>
                  {d.recientes.map((p) => {
                    const ev = estadoVisual(p.estado);
                    return (
                      <tr key={p.pedido_id}>
                        <td className="mono">#{idCorto(p.pedido_id)}</td>
                        <td><span className={`estado-badge estado-badge--${ev.clase}`}>{ev.etiqueta}</span></td>
                        <td>{p.items}</td>
                        <td>{precio(p.total)}</td>
                        <td className="tabla-ped__fecha">
                          {p.creado_en ? new Date(p.creado_en).toLocaleString("es-AR") : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
