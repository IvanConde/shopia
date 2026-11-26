"""Carga de herramientas desde el servidor MCP de dominio.

Usa los adaptadores de LangChain para MCP: descubre las herramientas que el
servidor publica (buscar_productos, consultar_estado_pedido, historial_pedidos)
y las devuelve como herramientas de LangChain que el agente puede invocar.
"""
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import settings

log = logging.getLogger("agente.mcp")

# Herramientas cacheadas por usuario: cada juego lleva su cabecera `X-User-Id`,
# que el servidor MCP reenvía a Pedidos para la autorización por dueño.
# La clave `None` es el juego sin identidad (uso interno / sin autenticación).
_tools_por_usuario: dict[str | None, list] = {}


async def cargar_tools(usuario_id: str | None = None) -> list:
    """Descubre (y cachea por usuario) las herramientas MCP. Si hay `usuario_id`,
    la conexión al servidor MCP viaja con la cabecera `X-User-Id`."""
    if usuario_id in _tools_por_usuario:
        return _tools_por_usuario[usuario_id]

    conexion = {"url": settings.mcp_url, "transport": "streamable_http"}
    if usuario_id:
        conexion["headers"] = {"X-User-Id": usuario_id}
    client = MultiServerMCPClient({"pfi": conexion})
    tools = await client.get_tools()
    _tools_por_usuario[usuario_id] = tools
    log.info("Herramientas MCP descubiertas (usuario=%s): %s",
             usuario_id or "-", [t.name for t in tools])
    return tools


async def tools_por_nombre(usuario_id: str | None = None) -> dict:
    return {t.name: t for t in await cargar_tools(usuario_id)}
