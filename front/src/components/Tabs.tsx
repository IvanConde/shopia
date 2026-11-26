import { useRef, type ReactNode } from "react";

export interface Pestana {
  id: string;
  etiqueta: string;
  icono?: string;
  contenido: ReactNode;
}

interface Props {
  pestanas: Pestana[];
  etiqueta: string;
  activa: string;
  onActiva: (id: string) => void;
}

/** Pestañas accesibles (patrón ARIA tabs): roving tabindex + navegación con
 *  flechas/Home/End. Controlado desde arriba (la pestaña activa la maneja App,
 *  para poder cambiarla por acciones como "comprar"). Los paneles se mantienen
 *  montados (hidden) para no perder el estado de cada pantalla. */
export default function Tabs({ pestanas, etiqueta, activa, onActiva }: Props) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function foco(id: string) {
    onActiva(id);
    refs.current[id]?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent, idx: number) {
    const n = pestanas.length;
    let destino = -1;
    if (e.key === "ArrowRight") destino = (idx + 1) % n;
    else if (e.key === "ArrowLeft") destino = (idx - 1 + n) % n;
    else if (e.key === "Home") destino = 0;
    else if (e.key === "End") destino = n - 1;
    if (destino >= 0) { e.preventDefault(); foco(pestanas[destino].id); }
  }

  return (
    <div className="tabs">
      <div className="tablist" role="tablist" aria-label={etiqueta}>
        {pestanas.map((p, i) => {
          const sel = activa === p.id;
          return (
            <button
              key={p.id}
              role="tab"
              id={`tab-${p.id}`}
              aria-selected={sel}
              aria-controls={`panel-${p.id}`}
              tabIndex={sel ? 0 : -1}
              className={`tab ${sel ? "tab--activa" : ""}`}
              ref={(el) => { refs.current[p.id] = el; }}
              onClick={() => onActiva(p.id)}
              onKeyDown={(e) => onKeyDown(e, i)}
            >
              {p.icono && <span className="tab__icono" aria-hidden="true">{p.icono}</span>}
              {p.etiqueta}
            </button>
          );
        })}
      </div>

      {pestanas.map((p) => (
        <div
          key={p.id}
          role="tabpanel"
          id={`panel-${p.id}`}
          aria-labelledby={`tab-${p.id}`}
          hidden={activa !== p.id}
          className="tabpanel"
        >
          {p.contenido}
        </div>
      ))}
    </div>
  );
}
