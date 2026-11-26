import { useEffect, useRef, useState, type ReactNode } from "react";
import TracePanel from "./TracePanel";
import { preguntar } from "../api";
import type { Mensaje, PasoTraza } from "../types";

// Render mínimo del markdown que devuelve el modelo: **negrita** y `código`.
function renderMarkdown(texto: string): ReactNode[] {
  const nodos: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|`([^`]+)`/g;
  let ultimo = 0;
  let k = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(texto)) !== null) {
    if (m.index > ultimo) nodos.push(texto.slice(ultimo, m.index));
    if (m[1] !== undefined) nodos.push(<strong key={k++}>{m[1]}</strong>);
    else nodos.push(<code key={k++} className="md-code">{m[2]}</code>);
    ultimo = m.index + m[0].length;
  }
  if (ultimo < texto.length) nodos.push(texto.slice(ultimo));
  return nodos;
}

const SUGERENCIAS = [
  "quiero auriculares aura",
  "¿hay stock de los auriculares aura lite?",
  "mostrame mi historial de compras",
];

export default function Chat({ listo }: { listo: boolean }) {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [entrada, setEntrada] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [traza, setTraza] = useState<PasoTraza[]>([]);
  const [visibles, setVisibles] = useState(0);
  const [backend, setBackend] = useState<string | null>(null);

  const finConversacion = useRef<HTMLDivElement>(null);
  const revelador = useRef<number | null>(null);

  useEffect(() => {
    finConversacion.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes, enviando]);

  useEffect(() => () => { if (revelador.current) window.clearInterval(revelador.current); }, []);

  function revelarTraza(pasos: PasoTraza[]) {
    if (revelador.current) window.clearInterval(revelador.current);
    setTraza(pasos);
    setVisibles(0);
    if (pasos.length === 0) return;
    let i = 0;
    revelador.current = window.setInterval(() => {
      i += 1;
      setVisibles(i);
      if (i >= pasos.length && revelador.current) {
        window.clearInterval(revelador.current);
        revelador.current = null;
      }
    }, 600);
  }

  async function enviar(texto: string) {
    const mensaje = texto.trim();
    if (!mensaje || enviando || !listo) return;
    setMensajes((m) => [...m, { rol: "usuario", texto: mensaje }]);
    setEntrada("");
    setEnviando(true);
    setTraza([]);
    setVisibles(0);
    try {
      const r = await preguntar(mensaje);
      setBackend(r.backend);
      setMensajes((m) => [...m, { rol: "asistente", texto: r.respuesta }]);
      revelarTraza(r.traza);
    } catch {
      setMensajes((m) => [
        ...m,
        { rol: "asistente", texto: "Tuve un problema para responder. Reintentá en unos segundos." },
      ]);
    } finally {
      setEnviando(false);
    }
  }

  const badgeClase = backend?.startsWith("gemini") ? "badge badge--live" : "badge badge--local";

  return (
    <div className="chat-layout">
      <section className="chat" aria-label="Conversación con el asistente">
        <div className="chat__mensajes" aria-live="polite">
          {mensajes.length === 0 && (
            <div className="vacio">
              <p className="vacio__titulo">Preguntale al asistente</p>
              <p className="vacio__texto">
                Consultá el estado de un pedido, tu historial o buscá productos.
                El asistente razona con herramientas reales y vas a ver cada paso
                en el panel de la derecha.
              </p>
            </div>
          )}

          {mensajes.map((m, i) => (
            <div
              key={i}
              className={`burbuja burbuja--${m.rol}`}
            >
              {m.rol === "asistente" ? renderMarkdown(m.texto) : m.texto}
            </div>
          ))}

          {enviando && (
            <div className="burbuja burbuja--asistente burbuja--typing" aria-label="El asistente está escribiendo">
              <span className="punto" />
              <span className="punto" />
              <span className="punto" />
            </div>
          )}
          <div ref={finConversacion} />
        </div>

        <div className="sugerencias" role="group" aria-label="Consultas sugeridas">
          {SUGERENCIAS.map((s) => (
            <button key={s} className="chip" disabled={enviando || !listo} onClick={() => enviar(s)}>
              {s}
            </button>
          ))}
        </div>

        <form className="entrada" onSubmit={(e) => { e.preventDefault(); enviar(entrada); }}>
          <label className="sr-only" htmlFor="chat-input">Escribí tu consulta</label>
          <input
            id="chat-input"
            type="text"
            placeholder="Escribí tu consulta…"
            value={entrada}
            onChange={(e) => setEntrada(e.target.value)}
            disabled={enviando || !listo}
          />
          <button type="submit" className="btn-primario" disabled={enviando || !listo || !entrada.trim()}>
            Enviar
          </button>
        </form>
        {backend && (
          <p className="chat__backend">
            <span className={badgeClase}>{backend.startsWith("gemini") ? "Gemini" : "Motor local"}</span>
            Respuesta generada por el backend indicado.
          </p>
        )}
      </section>

      <TracePanel pasos={traza} visibles={visibles} pensando={enviando} />
    </div>
  );
}
