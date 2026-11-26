import { useEffect, useState } from "react";

// Banner del "modo evento" (CyberMonday) con contador regresivo. Es un activo de
// demo/relato: refuerza la narrativa del pico de demanda. Los descuentos del
// catálogo son precios de referencia de ejemplo (rotulado acá, una sola vez).
const INICIO = 5 * 3600 + 59 * 60 + 59; // 05:59:59

function dos(n: number): string {
  return String(n).padStart(2, "0");
}

export default function BannerEvento() {
  const [seg, setSeg] = useState(INICIO);

  useEffect(() => {
    const t = window.setInterval(() => setSeg((s) => (s > 0 ? s - 1 : INICIO)), 1000);
    return () => window.clearInterval(t);
  }, []);

  const h = Math.floor(seg / 3600);
  const m = Math.floor((seg % 3600) / 60);
  const s = seg % 60;

  return (
    <>
      <div className="evento-banner" role="region" aria-label="Evento CyberMonday de ShopIA">
        <div className="evento-banner__main">
          <span className="evento-banner__flama" aria-hidden="true">🔥</span>
          <div className="evento-banner__texto">
            <p className="evento-banner__tit">CyberMonday ShopIA · Ofertas por tiempo limitado</p>
            <p className="evento-banner__sub">
              Descuentos en todo el catálogo
              <span className="tag-ejemplo">precios de referencia de ejemplo</span>
            </p>
          </div>
        </div>
        <div className="evento-banner__timer" aria-label="Tiempo restante de las ofertas">
          <span className="evento-banner__timer-lbl">Termina en</span>
          <span className="evento-banner__reloj" aria-live="off">
            <b>{dos(h)}</b><i>:</i><b>{dos(m)}</b><i>:</i><b>{dos(s)}</b>
          </span>
        </div>
      </div>
      <ul className="evento-benes" aria-label="Beneficios del evento">
        <li className="evento-bene"><span aria-hidden="true">🚚</span> Envío gratis</li>
        <li className="evento-bene"><span aria-hidden="true">💳</span> Cuotas sin interés</li>
        <li className="evento-bene"><span aria-hidden="true">⚡</span> Ofertas del día</li>
        <li className="evento-bene"><span aria-hidden="true">🔒</span> Compra protegida</li>
      </ul>
    </>
  );
}
