"""Medición del agente conversacional.

Lanza un conjunto fijo de consultas al agente a través del API Gateway y mide:
  * **% de consultas correctas**: el agente invoca la herramienta MCP adecuada
    (búsqueda de productos, stock por id, o estado de pedido por id) — se verifica
    en la traza ReAct devuelta. Objetivo: ≥ 90 %.
  * **latencia p50/p95/máx** por respuesta. Objetivo: p95 < 5 s.

Se corre desde el host (necesita `httpx`), con el stack levantado:
    python bench/medir_oe3_agente.py
Variables: GATEWAY_URL (def. http://127.0.0.1).
"""

import os
import statistics
import time

import httpx

GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1")
USUARIO = "11111111-1111-1111-1111-111111111111"


def _token(c):
    r = c.post("/api/auth/login", json={"email": "juan@shopia.demo", "password": "demo"})
    r.raise_for_status()
    return r.json()["access_token"]


def _preparar(c, headers):
    productos = c.get("/api/catalogo/productos", params={"q": ""}).json()
    pids = [p["id"] for p in productos[:2]] or [productos[0]["id"]]
    oids = []
    for _ in range(3):
        r = c.post("/api/pedidos", headers=headers,
                   json={"usuario_id": USUARIO, "items": [{"producto_id": pids[0], "cantidad": 1}]})
        oids.append(r.json()["id"])
    return pids, oids


def _consultas(pids, oids):
    busquedas = ["quiero auriculares aura", "busco un teclado", "mostrame mouse",
                 "necesito un monitor", "hay cámaras web", "quiero un parlante",
                 "busco cargador", "tenés notebooks"]
    q = [(t, "buscar_productos") for t in busquedas]
    for pid in (pids * 3)[:6]:
        q.append((f"hay stock del producto {pid}", "consultar_stock"))
    for oid in (oids * 2)[:6]:
        q.append((f"cuál es el estado del pedido {oid}", "consultar_estado_pedido"))
    return q


def main():
    with httpx.Client(base_url=GATEWAY, timeout=30.0) as c:
        headers = {"Authorization": f"Bearer {_token(c)}"}
        pids, oids = _preparar(c, headers)
        consultas = _consultas(pids, oids)

        correctas, latencias, detalle = 0, [], []
        for i, (msg, tool_esperada) in enumerate(consultas):
            t0 = time.perf_counter()
            r = c.post("/api/agente/chat", headers=headers,
                       json={"mensaje": msg, "session_id": f"bench-{i}"})
            dt = time.perf_counter() - t0
            latencias.append(dt)
            acciones = " ".join(p.get("accion", "") for p in r.json().get("traza", []))
            ok = tool_esperada in acciones
            correctas += ok
            detalle.append((ok, tool_esperada, f"{dt:.2f}s", msg[:40]))
            time.sleep(1.0)  # no saturar el free tier de Gemini

        n = len(consultas)
        lat_ord = sorted(latencias)
        p50 = statistics.median(lat_ord)
        p95 = lat_ord[max(0, int(round(0.95 * n)) - 1)]
        print("=== Agente conversacional (consultas correctas + latencia) ===")
        print(f"Consultas: {n}")
        print(f"Correctas (herramienta adecuada): {correctas}/{n} = {correctas/n*100:.1f} %  "
              f"(objetivo ≥ 90 %)  {'CUMPLE' if correctas/n >= 0.90 else 'NO CUMPLE'}")
        print(f"Latencia  p50={p50:.2f}s  p95={p95:.2f}s  máx={lat_ord[-1]:.2f}s  "
              f"(objetivo p95 < 5 s)  {'CUMPLE' if p95 < 5 else 'NO CUMPLE'}")
        print("\nDetalle:")
        for ok, tool, dt, msg in detalle:
            print(f"  [{'OK ' if ok else 'XX '}] {tool:24} {dt:>6}  «{msg}»")


if __name__ == "__main__":
    main()
