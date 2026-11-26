import { useEffect, useRef, useState } from "react";
import { listarNotificaciones } from "../api";
import type { Notificacion } from "../types";
import { haceTiempo, backendNotif } from "../util";

// Campana de notificaciones del comprador. Muestra los avisos generados por el
// motor adaptativo: texto redactado por IA (Gemini) con guardrails,
// o plantilla de respaldo — el badge deja ver cómo se generó cada uno.
export default function Campana({ refresco }: { refresco: number }) {
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<Notificacion[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  async function cargar() {
    setItems(await listarNotificaciones());
  }

  useEffect(() => { cargar(); }, [refresco]);
  useEffect(() => { if (abierto) cargar(); }, [abierto]);

  // Cerrar al hacer clic fuera del panel.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setAbierto(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const n = items.length;

  return (
    <div className="campana" ref={ref}>
      <button
        className="campana__btn"
        onClick={() => setAbierto((a) => !a)}
        aria-label={`Notificaciones (${n})`}
        aria-expanded={abierto}
      >
        🔔{n > 0 && <span className="campana__n">{n > 9 ? "9+" : n}</span>}
      </button>

      {abierto && (
        <div className="campana__panel" role="region" aria-label="Notificaciones">
          <p className="campana__tit">Notificaciones</p>
          {items.length === 0 ? (
            <p className="campana__vacio">
              No tenés notificaciones todavía. Hacé una compra y el motor te genera un aviso.
            </p>
          ) : (
            <ul className="campana__lista">
              {items.map((x) => {
                const b = backendNotif(x.backend);
                return (
                  <li key={x.id} className="notif">
                    <p className="notif__asunto">{x.asunto}</p>
                    <p className="notif__msg">{x.mensaje}</p>
                    <p className="notif__meta">
                      <span className={`notif__backend notif__backend--${b.clase}`}>{b.etiqueta}</span>
                      <span className="notif__canal">{x.canal}</span>
                      <span className="notif__hora">{haceTiempo(x.creado_en)}</span>
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
