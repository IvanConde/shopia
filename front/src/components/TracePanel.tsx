import type { PasoTraza } from "../types";

interface Props {
  pasos: PasoTraza[];
  visibles: number; // cuántos pasos revelar (animación escalonada)
  pensando: boolean;
}

// Panel lateral que muestra el razonamiento ReAct del agente paso a paso:
// pensamiento → acción (herramienta MCP) → observación (dato real devuelto).
export default function TracePanel({ pasos, visibles, pensando }: Props) {
  const mostrar = pasos.slice(0, visibles);

  return (
    <aside className="traza">
      <header className="traza__head">
        <h2>Razonamiento del agente</h2>
        <p className="traza__sub">
          Patrón ReAct · herramientas MCP sobre datos reales
        </p>
      </header>

      <div className="traza__cuerpo">
        {pasos.length === 0 && !pensando && (
          <p className="traza__vacio">
            Cada consulta muestra acá los pasos que da el agente: qué piensa,
            qué herramienta invoca y qué le devuelve el dominio.
          </p>
        )}

        {pensando && (
          <div className="traza__pensando">
            <span className="punto" />
            <span className="punto" />
            <span className="punto" />
            <span>razonando…</span>
          </div>
        )}

        {mostrar.map((p) => (
          <article key={p.paso} className="paso">
            <div className="paso__num">Paso {p.paso}</div>

            <div className="paso__bloque">
              <span className="paso__label">🧠 Pensamiento</span>
              <p className="paso__texto">{p.pensamiento}</p>
            </div>

            <div className="paso__bloque">
              <span className="paso__label">⚙️ Acción (herramienta MCP)</span>
              <code className="paso__accion">{p.accion}</code>
            </div>

            {p.observacion != null && (
              <div className="paso__bloque">
                <span className="paso__label">👁️ Observación (dato real)</span>
                <pre className="paso__obs">{p.observacion}</pre>
              </div>
            )}
          </article>
        ))}
      </div>
    </aside>
  );
}
