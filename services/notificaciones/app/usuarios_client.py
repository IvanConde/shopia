"""Cliente HTTP hacia el servicio de Usuarios (consulta de perfil).

El motor de notificaciones adapta el tono y el canal al perfil del comprador
(segmento + canal preferido). Si Usuarios no está disponible o el
usuario no existe, se degrada a valores por defecto (no rompe la notificación).
"""

import logging

import httpx

from .config import settings

log = logging.getLogger("notificaciones.usuarios")

_PERFIL_DEFECTO = {"segmento": "desconocido", "canal_preferido": "email", "nombre": None}


async def obtener_perfil(usuario_id: str | None) -> dict:
    """Devuelve {segmento, canal_preferido, nombre} del usuario, o valores por
    defecto si no se puede resolver."""
    if not usuario_id:
        return dict(_PERFIL_DEFECTO)
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.get(f"{settings.usuarios_url}/usuarios/{usuario_id}")
        if resp.status_code == 200:
            p = resp.json()
            return {
                "segmento": p.get("segmento") or "desconocido",
                "canal_preferido": p.get("canal_preferido") or "email",
                "nombre": p.get("nombre"),
            }
        return dict(_PERFIL_DEFECTO)
    except httpx.HTTPError as exc:
        log.warning("No se pudo consultar el perfil %s: %s", usuario_id, exc)
        return dict(_PERFIL_DEFECTO)
