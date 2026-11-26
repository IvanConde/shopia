"""Generación de la notificación adaptativa.

Estrategia:
  1. Se clasifica el evento en un **arquetipo** = tipo de evento + rango de monto +
     **segmento del cliente** + **canal preferido** (el tono y el canal se
     adaptan al perfil del usuario, que se consulta al servicio de Usuarios).
  2. Se busca en Redis una **plantilla** ya generada para ese arquetipo (caché).
  3. Si no está, se pide al **LLM** una plantilla con marcadores `{pedido}` y
     `{monto}`, adaptada al segmento y al canal, se le aplican **guardrails** y se
     cachea.
  4. Si el LLM no está disponible o no pasa los guardrails, se usa una **plantilla
     de respaldo** determinista (mismos marcadores).
  5. La plantilla se **personaliza** con los datos concretos del pedido.

Eventos que generan notificación: creación del pedido (`pedidos.creados`),
resultado del pago (`pagos.completados`/`pagos.rechazados`) y alerta de fraude
(`alertas.fraude`, dirigida al operador). Cachear la plantilla (y no el texto
final) permite reusar el trabajo del modelo entre notificaciones del mismo
arquetipo sin perder la personalización por pedido.
"""

import logging

from .config import settings
from . import redis_cache

log = logging.getLogger("notificaciones.generador")

# --- Guardrails ---
_MAX_LEN = 600
_PROHIBIDOS = ("```", "http://", "https://", "@")

# Evento del bus -> arquetipo de notificación.
_ESTADO_POR_RK = {
    "pedidos.creados": "creado",
    "pagos.completados": "aprobado",
    "pagos.rechazados": "rechazado",
    "alertas.fraude": "fraude",
}

_ASUNTOS = {
    "creado": "Recibimos tu pedido",
    "aprobado": "Confirmamos tu pago",
    "rechazado": "Tuvimos un problema con tu pago",
    "fraude": "Alerta: transacción a revisar",
}

# Tono por arquetipo para guiar al LLM.
_TONO = {
    "creado": "cordial, agradeciendo la compra y confirmando la recepción del pedido",
    "aprobado": "cordial y celebratorio",
    "rechazado": "empático y tranquilizador, ofreciendo reintentar el pago",
    "fraude": ("de alerta operativa dirigida al equipo de la tienda (no al cliente), "
               "informando de forma objetiva una transacción a revisar"),
}

# --- Plantillas de respaldo (determinista, sin LLM) ---
_FALLBACK = {
    "creado": (
        "¡Gracias por tu compra! Registramos tu pedido {pedido} por ${monto} y "
        "ya lo estamos procesando. Te avisaremos cuando se confirme el pago."
    ),
    "aprobado": (
        "¡Gracias por tu compra! Confirmamos el pago de tu pedido {pedido} "
        "por ${monto}. Ya lo estamos preparando y te avisaremos cuando se despache."
    ),
    "rechazado": (
        "No pudimos procesar el pago de tu pedido {pedido} por ${monto}. "
        "No te preocupes: podés reintentar el pago desde tu cuenta cuando quieras."
    ),
    "fraude": (
        "Se detectó una transacción potencialmente anómala en el pedido {pedido} "
        "por ${monto}. Revisá el caso en el panel de alertas de fraude."
    ),
}


def _bucket(monto: float) -> str:
    if monto < 100_000:
        return "bajo"
    if monto < 300_000:
        return "medio"
    return "alto"


def _fmt_monto(monto: float) -> str:
    # Formato local: punto como separador de miles (74999 -> "74.999").
    return "{:,.0f}".format(float(monto)).replace(",", ".")


def _aplicar_guardrails(texto: str) -> tuple[bool, str, str]:
    """Valida y sanea el texto del LLM. Devuelve (ok, texto_saneado, motivo)."""
    limpio = (texto or "").strip().strip('"').strip()
    if not limpio:
        return False, "", "vacío"
    if len(limpio) > _MAX_LEN:
        return False, "", f"excede {_MAX_LEN} caracteres"
    bajo = limpio.lower()
    for prohibido in _PROHIBIDOS:
        if prohibido in bajo:
            return False, "", f"contiene «{prohibido}»"
    # Garantiza que los datos del pedido queden presentes aunque el modelo los omita.
    if "{pedido}" not in limpio:
        limpio += " (Pedido {pedido}, total ${monto}.)"
    return True, limpio, "ok"


def _ajuste_canal(canal: str) -> str:
    if canal in ("sms", "push"):
        return f"El canal es {canal}: sé muy breve, una sola oración."
    if canal == "whatsapp":
        return "El canal es WhatsApp: tono cercano y breve (1 a 2 oraciones)."
    return "El canal es email: 2 a 3 oraciones."


async def _plantilla_llm(estado: str, bucket: str, segmento: str, canal: str) -> str | None:
    """Pide al LLM una plantilla con marcadores, adaptada al segmento y al canal;
    None si falla o no pasa guardrails."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        tono = _TONO.get(estado, "cordial y claro")
        sistema = (
            "Sos el motor de notificaciones de ShopIA, una tienda de electrónica. "
            "Redactás avisos claros en español rioplatense, sin tecnicismos. Adaptás "
            "el tono y la formalidad al segmento del destinatario y la longitud al canal. "
            "Respondé SOLO con el texto del aviso, sin comillas ni encabezados. Insertá "
            "los marcadores literales {pedido} y {monto} donde correspondan. No inventes "
            "datos, no incluyas enlaces ni direcciones de correo."
        )
        usuario = (
            f"Generá una plantilla de notificación para el evento **{estado}** "
            f"de monto {bucket}. Segmento del destinatario: {segmento}. "
            f"Tono: {tono}. {_ajuste_canal(canal)}"
        )
        llm = ChatGoogleGenerativeAI(
            model=settings.modelo_gemini,
            google_api_key=settings.gemini_api_key,
            temperature=0.4,
            max_retries=1,
        )
        msg = await llm.ainvoke([("system", sistema), ("user", usuario)])
        ok, saneado, motivo = _aplicar_guardrails(_a_texto(msg.content))
        if not ok:
            log.warning("Plantilla del LLM descartada por guardrails (%s); se usa respaldo.", motivo)
            return None
        return saneado
    except Exception as exc:  # noqa: BLE001 - degradación al respaldo
        log.warning("LLM no disponible (%s); se usa la plantilla de respaldo.", exc)
        return None


def _a_texto(content) -> str:
    """Normaliza el content de un mensaje LangChain a texto plano (str o bloques)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        partes = [(b.get("text") or "") if isinstance(b, dict) else str(b) for b in content]
        return "".join(partes).strip()
    return str(content or "")


async def _obtener_plantilla(estado: str, bucket: str, segmento: str, canal: str) -> tuple[str, str]:
    """Devuelve (plantilla, backend) resolviendo caché -> LLM -> respaldo. El
    arquetipo (clave de caché) incluye segmento y canal: distintos perfiles reciben
    textos distintos, pero se reutilizan entre usuarios del mismo arquetipo."""
    clave = f"notif:plantilla:{estado}:{bucket}:{segmento}:{canal}"

    if settings.backend == "gemini":
        cacheada = await redis_cache.obtener(clave)
        if cacheada:
            return cacheada, "cache"
        generada = await _plantilla_llm(estado, bucket, segmento, canal)
        if generada is not None:
            await redis_cache.guardar(clave, generada)
            return generada, "gemini"

    return _FALLBACK[estado], "fallback"


async def generar(routing_key: str, payload: dict, perfil: dict | None = None) -> dict:
    """Arma la notificación final para un evento del bus, adaptada al perfil.

    `perfil` (segmento + canal_preferido) lo resuelve el consumidor contra el
    servicio de Usuarios. La alerta de fraude se dirige al operador (canal interno),
    no al cliente.
    """
    estado = _ESTADO_POR_RK.get(routing_key, "aprobado")
    perfil = perfil or {}
    pedido_id = payload.get("pedido_id")
    usuario_id = payload.get("usuario_id")
    # El evento de creación transporta `total`; los de pago, `monto`.
    monto = payload.get("monto")
    if monto is None:
        monto = payload.get("total") or 0

    if estado == "fraude":
        segmento, canal = "operador", "interno"
    else:
        segmento = perfil.get("segmento") or "desconocido"
        canal = perfil.get("canal_preferido") or "email"

    plantilla, backend = await _obtener_plantilla(estado, _bucket(monto), segmento, canal)
    pedido_corto = str(pedido_id)[:8] if pedido_id else "—"
    mensaje = plantilla.replace("{pedido}", pedido_corto).replace("{monto}", _fmt_monto(monto))

    return {
        "usuario_id": usuario_id,
        "pedido_id": pedido_id,
        "canal": canal,
        "asunto": _ASUNTOS[estado],
        "mensaje": mensaje,
        "evento": routing_key,
        "backend": backend,
        "segmento": segmento,
    }
