import { useEffect, useState } from "react";
import Chat from "./components/Chat";
import Buscar from "./components/Buscar";
import Detalle from "./components/Detalle";
import Checkout from "./components/Checkout";
import BannerEvento from "./components/BannerEvento";
import Vendedor from "./components/Vendedor";
import Campana from "./components/Campana";
import MisPedidos from "./components/MisPedidos";
import Tabs, { type Pestana } from "./components/Tabs";
import { login, USUARIO_DEMO } from "./api";
import type { CarritoItem, Pedido, Producto } from "./types";

type Arranque = "cargando" | "listo" | "error";

export default function App() {
  const [arranque, setArranque] = useState<Arranque>("cargando");
  const [tab, setTab] = useState("buscar");
  const [refrescoPedidos, setRefrescoPedidos] = useState(0);
  const [pedidoNuevo, setPedidoNuevo] = useState<Pedido | null>(null);
  const [productoSel, setProductoSel] = useState<Producto | null>(null);
  const [carrito, setCarrito] = useState<CarritoItem[]>(() => {
    // Carrito persistente por visitante: sobrevive recargas de la página.
    try {
      const raw = localStorage.getItem("shopia_carrito");
      return raw ? (JSON.parse(raw) as CarritoItem[]) : [];
    } catch { return []; }
  });
  const [enCheckout, setEnCheckout] = useState(false);
  const [enVendedor, setEnVendedor] = useState(false);
  // Modo evento (CyberMonday): conmuta entre la tienda normal y la versión de
  // evento (banner + contador + precios en oferta). Preferencia por visitante.
  const [evento, setEvento] = useState<boolean>(() => {
    try { return localStorage.getItem("shopia_evento") === "1"; } catch { return false; }
  });

  useEffect(() => {
    (async () => {
      try {
        await login();
        setArranque("listo");
      } catch {
        setArranque("error");
      }
    })();
  }, []);

  useEffect(() => {
    try { localStorage.setItem("shopia_evento", evento ? "1" : "0"); } catch { /* sin storage */ }
  }, [evento]);

  useEffect(() => {
    try { localStorage.setItem("shopia_carrito", JSON.stringify(carrito)); } catch { /* sin storage */ }
  }, [carrito]);

  // Agrega (o acumula) un producto al carrito.
  function agregarAlCarrito(producto: Producto, cantidad: number) {
    setCarrito((prev) => {
      const i = prev.findIndex((c) => c.producto.id === producto.id);
      if (i >= 0) {
        const copia = [...prev];
        copia[i] = { ...copia[i], cantidad: copia[i].cantidad + cantidad };
        return copia;
      }
      return [...prev, { producto, cantidad }];
    });
  }

  function quitarDelCarrito(productoId: string) {
    setCarrito((prev) => prev.filter((c) => c.producto.id !== productoId));
  }

  // "Comprar ahora": agrega y va directo al checkout.
  function comprarAhora(producto: Producto, cantidad: number) {
    agregarAlCarrito(producto, cantidad);
    setProductoSel(null);
    setEnCheckout(true);
  }

  // Tras pagar: vacía el carrito, muestra el pedido nuevo en "Mis pedidos" y
  // deja que se refresque para ver la transición de estado (event-driven).
  function alPagar(pedido: Pedido) {
    setCarrito([]);
    setEnCheckout(false);
    setProductoSel(null);
    setPedidoNuevo(pedido);
    setRefrescoPedidos((n) => n + 1);
    setTab("pedidos");
  }

  const unidades = carrito.reduce((s, c) => s + c.cantidad, 0);

  const pestanas: Pestana[] = [
    {
      id: "buscar", etiqueta: "Buscar", icono: "🔎",
      contenido: (
        <Buscar
          evento={evento}
          onVerProducto={setProductoSel}
          onComprar={(p) => comprarAhora(p, 1)}
          onIrAlAsistente={() => setTab("asistente")}
        />
      ),
    },
    {
      id: "pedidos", etiqueta: "Mis pedidos", icono: "📦",
      contenido: (
        <MisPedidos
          refresco={refrescoPedidos}
          nuevo={pedidoNuevo}
          onIrABuscar={() => setTab("buscar")}
          onIrAlAsistente={() => setTab("asistente")}
        />
      ),
    },
    { id: "asistente", etiqueta: "Asistente", icono: "💬", contenido: <Chat listo={true} /> },
  ];

  return (
    <div className={`app ${evento ? "app--evento" : ""}`}>
      <header className="cabecera">
        <a className="marca" href="/" aria-label="ShopIA — inicio">
          <span className="marca__iso" aria-hidden="true">🛍️</span>
          <span className="marca__nombre">
            Shop<span className="marca__ia">IA</span>
          </span>
        </a>
        <div className="cabecera__der">
          <button
            className={`vendedor-btn ${enVendedor ? "vendedor-btn--on" : ""}`}
            onClick={() => { setEnVendedor((v) => !v); setProductoSel(null); setEnCheckout(false); }}
            aria-pressed={enVendedor}
            title="Panel de vendedor (vista de operador)"
          >
            🏪 Vendedor
          </button>
          <button
            className={`evento-toggle ${evento ? "evento-toggle--on" : ""}`}
            onClick={() => setEvento((e) => !e)}
            aria-pressed={evento}
            title={evento ? "Volver a la tienda normal" : "Activar el evento CyberMonday"}
          >
            🔥 CyberMonday
          </button>
          <button
            className="carrito-btn"
            onClick={() => setEnCheckout(true)}
            disabled={unidades === 0}
            aria-label={`Carrito, ${unidades} ${unidades === 1 ? "artículo" : "artículos"}`}
          >
            🛒 Carrito{unidades > 0 && <span className="carrito-btn__n">{unidades}</span>}
          </button>
          <Campana refresco={refrescoPedidos} />
          <p className="sesion">
            <span className="sesion__label">Sesión</span>
            <span className="sesion__email">{USUARIO_DEMO.email}</span>
          </p>
        </div>
      </header>

      <main className="contenido" id="contenido">
        {arranque === "cargando" && (
          <div className="aviso" role="status">
            <span className="spinner" aria-hidden="true" />
            <p>Iniciando sesión en el prototipo…</p>
          </div>
        )}

        {arranque === "error" && (
          <div className="aviso aviso--error" role="alert">
            <p className="aviso__titulo">No pude conectar con el prototipo</p>
            <p>
              Verificá que el stack esté levantado
              (<code>cd infra &amp;&amp; docker compose up -d</code>) y recargá la página.
            </p>
            <button className="btn-primario" onClick={() => location.reload()}>
              Reintentar
            </button>
          </div>
        )}

        {arranque === "listo" && enVendedor && (
          <Vendedor
            evento={evento}
            onToggleEvento={() => setEvento((e) => !e)}
            onVolver={() => setEnVendedor(false)}
          />
        )}

        {arranque === "listo" && !enVendedor && evento && <BannerEvento />}

        {arranque === "listo" && !enVendedor && enCheckout && (
          <Checkout
            carrito={carrito}
            evento={evento}
            onQuitar={quitarDelCarrito}
            onVolver={() => setEnCheckout(false)}
            onIrABuscar={() => { setEnCheckout(false); setTab("buscar"); }}
            onPagado={alPagar}
          />
        )}

        {arranque === "listo" && !enVendedor && !enCheckout && productoSel && (
          <Detalle
            producto={productoSel}
            evento={evento}
            onVolver={() => setProductoSel(null)}
            onComprarAhora={comprarAhora}
            onAgregar={agregarAlCarrito}
            onIrAlAsistente={() => { setProductoSel(null); setTab("asistente"); }}
          />
        )}

        {arranque === "listo" && !enVendedor && !enCheckout && !productoSel && (
          <Tabs pestanas={pestanas} etiqueta="Secciones de ShopIA" activa={tab} onActiva={setTab} />
        )}
      </main>
    </div>
  );
}
