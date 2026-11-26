"""Servidor MCP de dominio.

Expone como *herramientas* del Model Context Protocol (MCP) las operaciones de
consulta de los microservicios de Catálogo y Pedidos. El agente conversacional
(patrón ReAct) las descubre y las invoca por transporte HTTP (streamable-http),
sin conocer los detalles internos de cada servicio.

En el diseño de destino cada microservicio hospedaría su propio servidor MCP;
para este spike se concentran en un único servidor que hace de fachada, lo cual
alcanza para demostrar el patrón agente ↔ MCP ↔ dominio con datos reales.
"""
import contextlib
import logging

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mcp-dominio")

# El agente llega por el nombre de servicio interno (mcp:8000). La protección
# anti DNS-rebinding valida el header Host y rechazaría ese origen (421); se
# desactiva porque el servidor es interno a la red de confianza (pfi_net) y su
# único cliente es el agente. El path por defecto del transporte es "/mcp".
mcp = FastMCP(
    "pfi-dominio",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


async def _get(url: str, params: dict | None = None, headers: dict | None = None):
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(url, params=params, headers=headers)
        return resp


def _reenvio_dueno(ctx: Context | None) -> dict | None:
    """Extrae `X-User-Id` de la request entrante (lo manda el agente) para
    reenviarlo a Pedidos y que aplique la autorización por dueño. Si no se
    puede obtener, devuelve None (Pedidos tratará la llamada como interna)."""
    try:
        req = ctx.request_context.request  # Starlette Request en transporte HTTP
        uid = req.headers.get("X-User-Id") if req is not None else None
        return {"X-User-Id": uid} if uid else None
    except Exception:  # noqa: BLE001 - ante cualquier variante del contexto, no se reenvía
        return None


async def _en_revision_fraude(pedido_id: str, headers: dict | None) -> bool:
    """True si el detector de anomalías tiene una alerta para este pedido.

    Consulta el servicio de anomalías reenviando `X-User-Id` (cada usuario
    solo ve sus alertas). Es mejor esfuerzo: ante cualquier fallo devuelve False y
    no interrumpe la consulta del estado del pedido."""
    try:
        resp = await _get(f"{settings.anomalias_url}/alertas", headers=headers)
        if resp.status_code != 200:
            return False
        return any(a.get("pedido_id") == pedido_id for a in resp.json())
    except Exception:  # noqa: BLE001
        return False


@mcp.tool()
async def buscar_productos(consulta: str) -> list[dict]:
    """Busca productos del catálogo por texto libre (nombre o descripción).

    Úsese cuando el usuario quiere encontrar artículos o consultar precios.
    Devuelve una lista de productos con id, nombre, descripción y precio.
    """
    resp = await _get(f"{settings.catalogo_url}/productos", params={"q": consulta})
    if resp.status_code != 200:
        return [{"error": f"Catálogo respondió {resp.status_code}"}]
    productos = resp.json()
    return [
        {
            "id": p["id"],
            "nombre": p["nombre"],
            "descripcion": p["descripcion"],
            "precio": p["precio"],
        }
        for p in productos
    ]


@mcp.tool()
async def consultar_estado_pedido(pedido_id: str, ctx: Context) -> dict:
    """Consulta el estado y el detalle de un pedido por su identificador (UUID).

    Úsese cuando el usuario pregunta cómo va, en qué estado está, cuándo llega, o
    **si un pedido quedó en revisión por fraude / como transacción sospechosa**.
    Devuelve estado, total, fecha estimada de entrega, cantidad de ítems y
    `en_revision_fraude` (True si el detector de anomalías marcó la transacción).
    """
    headers = _reenvio_dueno(ctx)
    resp = await _get(f"{settings.pedidos_url}/pedidos/{pedido_id}", headers=headers)
    if resp.status_code == 404:
        return {"error": "No existe un pedido con ese identificador."}
    if resp.status_code != 200:
        return {"error": f"Pedidos respondió {resp.status_code}"}
    p = resp.json()
    return {
        "pedido_id": p["id"],
        "estado": p["estado"],
        "total": p["total"],
        "fecha_estimada": p.get("fecha_estimada"),
        "cantidad_items": len(p.get("items", [])),
        "en_revision_fraude": await _en_revision_fraude(pedido_id, headers),
    }


@mcp.tool()
async def historial_pedidos(usuario_id: str, ctx: Context) -> list[dict]:
    """Lista el historial de pedidos de un usuario por su identificador (UUID).

    Úsese cuando el usuario pide ver sus pedidos anteriores o su historial de
    compras. Devuelve una lista con id, estado, total y fecha de creación.
    """
    # Pedidos usa el `X-User-Id` reenviado (dueño autenticado) y, cuando está
    # presente, ignora este `usuario_id` del texto.
    resp = await _get(f"{settings.pedidos_url}/pedidos", params={"usuario_id": usuario_id},
                      headers=_reenvio_dueno(ctx))
    if resp.status_code != 200:
        return [{"error": f"Pedidos respondió {resp.status_code}"}]
    return [
        {
            "pedido_id": p["id"],
            "estado": p["estado"],
            "total": p["total"],
            "creado_en": p["creado_en"],
        }
        for p in resp.json()
    ]


@mcp.tool()
async def consultar_stock(producto_id: str) -> dict:
    """Consulta la disponibilidad de stock de un producto por su identificador (UUID).

    Úsese cuando el usuario pregunta si hay stock, cuántas unidades quedan o si un
    producto está disponible. Devuelve las unidades disponibles y reservadas.
    """
    resp = await _get(f"{settings.stock_url}/stock/{producto_id}")
    if resp.status_code == 404:
        return {"error": "No hay registro de stock para ese producto."}
    if resp.status_code != 200:
        return {"error": f"Stock respondió {resp.status_code}"}
    s = resp.json()
    disponible = s.get("disponible", 0)
    return {
        "producto_id": s.get("producto_id"),
        "disponible": disponible,
        "reservado": s.get("reservado", 0),
        "hay_stock": disponible > 0,
    }


async def health(_request):
    return JSONResponse({"status": "ok", "service": "mcp"})


# El servidor de streamable-http trae su propio ciclo de vida (gestor de
# sesiones); hay que ejecutarlo dentro del lifespan de la app que lo monta.
@contextlib.asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        log.info("Servidor MCP listo (transport=streamable-http, path=/mcp)")
        yield


app = Starlette(
    routes=[
        Route("/health", health),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)
