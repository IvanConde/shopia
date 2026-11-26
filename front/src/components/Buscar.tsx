import { useEffect, useMemo, useState } from "react";
import { buscarProductos, consultarStock, listarCategorias } from "../api";
import type { Categoria, Producto } from "../types";
import { precio, gradiente, stockVisual, ofertaDemo, imagenProducto } from "../util";

type Estado = "cargando" | "listo" | "error";
type Orden = "relevancia" | "precio-asc" | "precio-desc";

export default function Buscar(
  { evento, onVerProducto, onComprar, onIrAlAsistente }:
  {
    evento?: boolean;
    onVerProducto?: (p: Producto) => void;
    onComprar?: (p: Producto) => void;
    onIrAlAsistente?: () => void;
  }
) {
  const [q, setQ] = useState("");
  const [productos, setProductos] = useState<Producto[]>([]);
  const [stock, setStock] = useState<Record<string, number | null>>({});
  const [categorias, setCategorias] = useState<Record<string, string>>({});
  const [estado, setEstado] = useState<Estado>("cargando");
  const [filtroCat, setFiltroCat] = useState<string>("todas");
  const [soloStock, setSoloStock] = useState(false);
  const [orden, setOrden] = useState<Orden>("relevancia");

  async function cargar(termino = "") {
    setEstado("cargando");
    try {
      const items = await buscarProductos(termino);
      setProductos(items);
      setEstado("listo");
      const pares = await Promise.all(
        items.map(async (p) => {
          try { const s = await consultarStock(p.id); return [p.id, s?.disponible ?? null] as const; }
          catch { return [p.id, null] as const; }
        })
      );
      setStock(Object.fromEntries(pares));
    } catch {
      setEstado("error");
    }
  }

  useEffect(() => { cargar(""); }, []);
  useEffect(() => {
    listarCategorias()
      .then((cats: Categoria[]) => setCategorias(Object.fromEntries(cats.map((c) => [c.id, c.nombre]))))
      .catch(() => { /* sin categorías: las tarjetas no muestran el tag */ });
  }, []);

  const visibles = useMemo(() => {
    let lista = productos;
    if (filtroCat !== "todas") lista = lista.filter((p) => p.categoria_id === filtroCat);
    if (soloStock) lista = lista.filter((p) => (stock[p.id] ?? 0) > 0);
    if (orden === "precio-asc") lista = [...lista].sort((a, b) => a.precio - b.precio);
    else if (orden === "precio-desc") lista = [...lista].sort((a, b) => b.precio - a.precio);
    return lista;
  }, [productos, filtroCat, soloStock, orden, stock]);

  const catsPresentes = useMemo(() => {
    const ids = new Set(productos.map((p) => p.categoria_id).filter(Boolean) as string[]);
    return [...ids].map((id) => ({ id, nombre: categorias[id] ?? "Otros" }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  }, [productos, categorias]);

  // Destacados del evento: los 3 productos con mayor descuento (solo en modo evento).
  const destacados = useMemo(() => {
    if (!evento) return [];
    return [...productos]
      .map((p) => ({ p, of: ofertaDemo(p.id, p.precio) }))
      .sort((a, b) => b.of.pct - a.of.pct)
      .slice(0, 3);
  }, [productos, evento]);

  return (
    <section className="buscar" aria-label="Búsqueda de productos">
      <form
        className="buscar__barra"
        role="search"
        onSubmit={(e) => { e.preventDefault(); cargar(q); }}
      >
        <label className="sr-only" htmlFor="buscar-input">Buscar productos</label>
        <input
          id="buscar-input"
          type="search"
          placeholder="Buscar productos (p. ej. auriculares, teclado)…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="submit" className="btn-primario">Buscar</button>
      </form>

      {estado === "listo" && productos.length > 0 && (
        <div className="filtros">
          <div className="filtros__cats" role="group" aria-label="Filtrar por categoría">
            <button className={`chip ${filtroCat === "todas" ? "chip--activo" : ""}`}
                    aria-pressed={filtroCat === "todas"} onClick={() => setFiltroCat("todas")}>
              Todas
            </button>
            {catsPresentes.map((c) => (
              <button key={c.id} className={`chip ${filtroCat === c.id ? "chip--activo" : ""}`}
                      aria-pressed={filtroCat === c.id} onClick={() => setFiltroCat(c.id)}>
                {c.nombre}
              </button>
            ))}
          </div>
          <div className="filtros__der">
            <label className="filtros__check">
              <input type="checkbox" checked={soloStock} onChange={(e) => setSoloStock(e.target.checked)} />
              Con stock
            </label>
            <label className="sr-only" htmlFor="orden">Ordenar</label>
            <select id="orden" className="filtros__orden" value={orden}
                    onChange={(e) => setOrden(e.target.value as Orden)}>
              <option value="relevancia">Relevancia</option>
              <option value="precio-asc">Precio: menor a mayor</option>
              <option value="precio-desc">Precio: mayor a menor</option>
            </select>
          </div>
        </div>
      )}

      {estado === "cargando" && (
        <div className="aviso" role="status"><span className="spinner" aria-hidden="true" /><p>Cargando catálogo…</p></div>
      )}

      {estado === "error" && (
        <div className="aviso aviso--error" role="alert">
          <p className="aviso__titulo">No pudimos cargar el catálogo</p>
          <button className="btn-primario" onClick={() => cargar(q)}>Reintentar</button>
        </div>
      )}

      {estado === "listo" && productos.length === 0 && (
        <div className="vacio">
          <p className="vacio__titulo">Sin resultados</p>
          <p className="vacio__texto">No encontramos productos para «{q}». Probá con otro término.</p>
          <button className="btn-primario" onClick={() => { setQ(""); cargar(""); }}>Ver todo el catálogo</button>
        </div>
      )}

      {estado === "listo" && productos.length > 0 && (
        <>
          {evento && destacados.length > 0 && (
            <section className="destacados" aria-label="Destacados del CyberMonday">
              <h2 className="destacados__tit">🔥 Destacados CyberMonday</h2>
              <div className="destacados__fila">
                {destacados.map(({ p, of }) => {
                  const dimg = imagenProducto(p.nombre);
                  return (
                    <button key={p.id} className="destacado" onClick={() => onVerProducto?.(p)}
                            aria-label={`Ver ${p.nombre}, ${of.pct}% de descuento`}>
                      <span className="destacado__img" style={dimg ? undefined : { background: gradiente(p.id) }}>
                        {dimg && <img src={dimg} alt="" loading="lazy" />}
                        <span className="destacado__off">-{of.pct}%</span>
                      </span>
                      <span className="destacado__nombre">{p.nombre}</span>
                      <span className="destacado__precios">
                        <span className="precio-lista">{precio(of.lista)}</span>
                        <span className="destacado__ahora">{precio(p.precio)}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          <p className="buscar__conteo">{visibles.length} {visibles.length === 1 ? "resultado" : "resultados"}</p>
          <ul className="grilla" aria-label="Resultados">
            {visibles.map((p) => {
              const disp = stock[p.id];
              const sv = stockVisual(disp);
              const sinStock = disp === 0;
              const cat = p.categoria_id ? categorias[p.categoria_id] : undefined;
              const of = evento ? ofertaDemo(p.id, p.precio) : null;
              const img = imagenProducto(p.nombre);
              return (
                <li key={p.id} className="tarjeta">
                  <button
                    className="tarjeta__imagen"
                    style={img ? undefined : { background: gradiente(p.id) }}
                    onClick={() => onVerProducto?.(p)}
                    aria-label={`Ver detalle de ${p.nombre}`}
                  >
                    {evento && <span className="tarjeta__ribbon" aria-hidden="true">OFERTA</span>}
                    {img && <img className="tarjeta__img" src={img} alt={p.nombre} loading="lazy" />}
                  </button>
                  <div className="tarjeta__cuerpo">
                    {cat && <span className="tarjeta__cat">{cat}</span>}
                    <button className="tarjeta__nombre tarjeta__nombre--link" onClick={() => onVerProducto?.(p)}>
                      {p.nombre}
                    </button>
                    {p.descripcion && <p className="tarjeta__desc">{p.descripcion}</p>}
                  </div>
                  <div className="tarjeta__pie">
                    <div>
                      <span className="tarjeta__precio-wrap">
                        {of && <span className="precio-lista">{precio(of.lista)}</span>}
                        <span className="tarjeta__precio">{precio(p.precio)}</span>
                        {of && <span className="precio-off">-{of.pct}%</span>}
                      </span>
                      <span className={`stock-badge stock-badge--${sv.clase}`}>{sv.etiqueta}</span>
                    </div>
                    <button
                      className="btn-primario"
                      onClick={() => onComprar?.(p)}
                      disabled={sinStock}
                      aria-label={`Comprar ${p.nombre}`}
                    >
                      Comprar
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="cta-asistente">
            <div>
              <p className="cta-asistente__tit">🤖 ¿No encontrás lo que buscás?</p>
              <p className="cta-asistente__txt">Describíselo al asistente: consulta el catálogo y el stock por vos.</p>
            </div>
            <button className="btn-secundario" onClick={() => onIrAlAsistente?.()}>Preguntar al asistente</button>
          </div>
        </>
      )}
    </section>
  );
}
