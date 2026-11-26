"""Agente conversacional con patrón ReAct.

Orquesta las herramientas MCP de dominio para responder consultas del comprador
(estado de un pedido, historial, búsqueda de productos) razonando qué
herramienta usar, invocándola y observando el resultado antes de responder.

Dos backends de razonamiento, seleccionados por configuración:
  * "gemini"   → modelo real (Google Gemini, free tier) sobre un grafo ReAct de
                 LangGraph. Es el modo objetivo del proyecto.
  * "fallback" → planificador determinista por reglas, que se activa cuando no
                 hay clave de API. Ejercita las mismas herramientas MCP y expone
                 la misma traza, para poder probar el andamiaje sin credenciales.
"""
import json
import logging
import re

from . import redis_store
from .circuit_breaker import CircuitBreaker
from .config import settings
from .mcp_tools import cargar_tools, tools_por_nombre

log = logging.getLogger("agente.core")

# Circuit breaker del backend Gemini: protege contra el LLM caído o sin
# cuota; cuando se abre, las consultas van directo al respaldo determinista.
_breaker_gemini = CircuitBreaker(
    umbral_fallos=settings.cb_umbral_fallos,
    cooldown_s=settings.cb_cooldown_s,
    nombre="gemini",
)

SYSTEM_PROMPT = (
    "Sos el asistente conversacional de ShopIA, una tienda de electrónica. "
    "Ayudás al comprador a consultar el estado de sus pedidos, su historial de "
    "compras, la disponibilidad de stock de un producto y a buscar productos. "
    "Respondés ÚNICAMENTE sobre ShopIA: productos de la tienda, stock, pedidos, "
    "historial y la cuenta del usuario. Si te preguntan cualquier otra cosa "
    "(programación, matemática, poemas, recetas, consejos o temas ajenos al "
    "comercio), NO la respondas: decliná amablemente en una sola frase y reencauzá "
    "hacia lo que sí podés ayudar; no uses conocimiento general para esos temas. "
    "Respondé en español, de forma breve y clara. "
    "Usá SIEMPRE las herramientas disponibles para obtener datos reales; nunca "
    "inventes estados, precios ni identificadores. Si falta un dato (por ejemplo "
    "el identificador del pedido), pedíselo al usuario."
)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


# --------------------------------------------------------------------------- #
# Backend Gemini (LangGraph create_react_agent)
# --------------------------------------------------------------------------- #
async def _responder_gemini(pregunta: str, usuario_id: str | None = None,
                            historial: list | None = None) -> dict:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langgraph.prebuilt import create_react_agent

    tools = await cargar_tools(usuario_id)
    llm = ChatGoogleGenerativeAI(
        model=settings.modelo_gemini,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        # Ante un error del proveedor, fallar rápido y degradar al respaldo en
        # vez de encadenar reintentos con backoff (que colgarían la respuesta).
        max_retries=1,
    )
    agente = create_react_agent(llm, tools)
    # Identidad del usuario autenticado: el gateway ya validó el JWT y propagó
    # `X-User-Id`. Se la damos al modelo para que complete el identificador en las
    # herramientas que lo requieren (p. ej. su historial) sin pedírselo. El servidor
    # MCP impone igual la autorización por dueño con ese mismo encabezado.
    system = SYSTEM_PROMPT
    if usuario_id:
        system += (
            f" El usuario autenticado tiene identificador {usuario_id}; usalo cuando "
            "una herramienta requiera el identificador del usuario (por ejemplo, su "
            "historial de compras) y nunca se lo pidas."
        )
    # Memoria conversacional: se antepone el historial (turnos previos) al mensaje
    # actual para que el modelo siga el hilo.
    mensajes_in = [("system", system)]
    mensajes_in += list(historial or [])
    mensajes_in.append(("user", pregunta))
    resultado = await agente.ainvoke({"messages": mensajes_in})
    mensajes = resultado["messages"]
    return {
        "backend": "gemini",
        "modelo": settings.modelo_gemini,
        "respuesta": _a_texto(mensajes[-1].content),
        "traza": _traza_desde_mensajes(mensajes),
    }


def _a_texto(content) -> str:
    """Normaliza el `content` de un mensaje a texto plano.

    Según el modelo, LangChain devuelve el contenido como str o como lista de
    bloques (`[{"type": "text", "text": ...}]`, p. ej. Gemini 3.x). Se concatena
    el texto de los bloques.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        partes = [
            (b.get("text") or "") if isinstance(b, dict) else str(b) for b in content
        ]
        return "".join(partes).strip()
    return str(content or "")


def _traza_desde_mensajes(mensajes) -> list[dict]:
    """Reconstruye la traza ReAct (pensamiento → acción → observación) a partir
    de la secuencia de mensajes que produjo el grafo."""
    traza: list[dict] = []
    for m in mensajes:
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                traza.append(
                    {
                        "paso": len(traza) + 1,
                        "pensamiento": _a_texto(getattr(m, "content", ""))
                        or "(razonamiento interno del modelo)",
                        "accion": f"{tc['name']}({tc['args']})",
                        "observacion": None,
                    }
                )
        elif m.__class__.__name__ == "ToolMessage":
            for entrada in reversed(traza):
                if entrada["observacion"] is None:
                    entrada["observacion"] = _a_texto(getattr(m, "content", ""))
                    break
    return traza


# --------------------------------------------------------------------------- #
# Backend de respaldo (planificador determinista por reglas)
# --------------------------------------------------------------------------- #
async def _responder_fallback(pregunta: str, usuario_id: str | None = None) -> dict:
    texto = pregunta.lower()
    uuid = _UUID_RE.search(pregunta)
    tools = await tools_por_nombre(usuario_id)

    quiere_historial = any(
        k in texto for k in ("historial", "mis pedidos", "mis compras", "todos mis")
    )
    quiere_stock = any(
        k in texto for k in ("stock", "disponib", "quedan", "unidades", "hay de")
    )
    quiere_pedido = any(
        k in texto for k in ("pedido", "estado", "envío", "envio", "llega", "entrega", "orden")
    )

    if uuid and quiere_stock:
        nombre, args = "consultar_stock", {"producto_id": uuid.group(0)}
    elif quiere_historial and (uuid or usuario_id):
        # El historial es del usuario autenticado: si no viene un UUID en el texto,
        # se usa el identificador propagado por el gateway (X-User-Id).
        nombre, args = "historial_pedidos", {"usuario_id": uuid.group(0) if uuid else usuario_id}
    elif uuid and (quiere_pedido or not quiere_historial):
        nombre, args = "consultar_estado_pedido", {"pedido_id": uuid.group(0)}
    else:
        # Sin identificador: se interpreta como búsqueda de productos.
        consulta = _limpiar_consulta(pregunta)
        nombre, args = "buscar_productos", {"consulta": consulta}

    tool = tools.get(nombre)
    if tool is None:
        return {
            "backend": "fallback",
            "modelo": "reglas",
            "respuesta": "No hay herramientas MCP disponibles en este momento.",
            "traza": [],
        }

    pensamiento = _pensamiento(nombre, args)
    cruda = await tool.ainvoke(args)
    datos = _parse_mcp(cruda)  # desempaqueta los bloques de contenido MCP
    respuesta = _redactar(nombre, datos)

    return {
        "backend": "fallback",
        "modelo": "reglas",
        "respuesta": respuesta,
        "traza": [
            {
                "paso": 1,
                "pensamiento": pensamiento,
                "accion": f"{nombre}({args})",
                "observacion": json.dumps(datos, ensure_ascii=False, indent=2),
            }
        ],
    }


def _parse_mcp(obs) -> list[dict]:
    """Normaliza el resultado de una herramienta MCP a una lista de objetos.

    Los adaptadores MCP devuelven el resultado como bloques de contenido
    (`[{"type": "text", "text": "<json>"}, ...]`); cada bloque trae un objeto
    serializado en JSON. Se parsea cada uno y se devuelve la lista resultante.
    """
    bloques = obs if isinstance(obs, list) else [obs]
    resultados: list[dict] = []
    for b in bloques:
        if isinstance(b, dict) and "text" in b:
            texto = b["text"]
        elif isinstance(b, dict):
            resultados.append(b)
            continue
        elif isinstance(b, str):
            texto = b
        else:
            texto = str(b)
        try:
            resultados.append(json.loads(texto))
        except (ValueError, TypeError):
            resultados.append({"texto": texto})
    return resultados


def _limpiar_consulta(pregunta: str) -> str:
    stop = {
        "quiero", "buscar", "busca", "busco", "producto", "productos", "precio",
        "precios", "de", "un", "una", "el", "la", "los", "las", "por", "favor",
        "me", "mostrar", "mostra", "ver", "sobre", "hay", "tienen", "tenes",
    }
    palabras = [p for p in re.findall(r"\w+", pregunta.lower()) if p not in stop]
    return " ".join(palabras).strip() or pregunta.strip()


def _pensamiento(nombre: str, args: dict) -> str:
    if nombre == "consultar_estado_pedido":
        return f"El usuario pregunta por un pedido concreto ({args['pedido_id'][:8]}…); consulto su estado."
    if nombre == "historial_pedidos":
        return "El usuario quiere su historial de compras; consulto sus pedidos."
    if nombre == "consultar_stock":
        return f"El usuario pregunta por disponibilidad de un producto ({args['producto_id'][:8]}…); consulto el stock."
    return f"El usuario busca productos; consulto el catálogo por «{args.get('consulta', '')}»."


def _hay_error(datos: list[dict]) -> bool:
    return not datos or (isinstance(datos[0], dict) and bool(datos[0].get("error")))


def _redactar(nombre: str, datos: list[dict]) -> str:
    if nombre == "consultar_estado_pedido":
        if _hay_error(datos):
            return datos[0].get("error", "No pude consultar el pedido.") if datos else "No pude consultar el pedido."
        d = datos[0]
        fecha = d.get("fecha_estimada") or "sin definir"
        return (
            f"Tu pedido {str(d.get('pedido_id', ''))[:8]} está en estado "
            f"«{d.get('estado')}». Total: ${d.get('total')}. "
            f"Entrega estimada: {fecha}."
        )
    if nombre == "historial_pedidos":
        if _hay_error(datos):
            return "No encontré pedidos en tu historial."
        return (
            f"Encontré {len(datos)} pedido(s) en tu historial. "
            f"El más reciente está en estado «{datos[0].get('estado')}» "
            f"por ${datos[0].get('total')}."
        )
    if nombre == "consultar_stock":
        if _hay_error(datos):
            return datos[0].get("error", "No pude consultar el stock.") if datos else "No pude consultar el stock."
        d = datos[0]
        if d.get("hay_stock"):
            return f"Sí, hay stock: quedan {d.get('disponible')} unidad(es) disponible(s)."
        return "No hay stock disponible de ese producto en este momento."
    # buscar_productos
    if _hay_error(datos):
        return "No encontré productos para esa búsqueda."
    items = ", ".join(f"{p.get('nombre')} (${p.get('precio')})" for p in datos[:3])
    return f"Encontré {len(datos)} producto(s). Por ejemplo: {items}."


# --------------------------------------------------------------------------- #
# Punto de entrada
# --------------------------------------------------------------------------- #
async def _responder_core(pregunta: str, usuario_id: str | None, historial: list) -> dict:
    """Resuelve con el backend configurado (Gemini con degradación al respaldo),
    protegido por un circuit breaker."""
    if settings.backend != "gemini":
        return await _responder_fallback(pregunta, usuario_id)

    # Circuito abierto: no se intenta Gemini, se degrada de inmediato.
    if not _breaker_gemini.permite():
        log.warning("Circuito Gemini ABIERTO; se responde con el respaldo sin intentar el LLM.")
        salida = await _responder_fallback(pregunta, usuario_id)
        salida["backend"] = "fallback (circuito abierto)"
        return salida

    try:
        resultado = await _responder_gemini(pregunta, usuario_id, historial)
        _breaker_gemini.registrar_exito()
        return resultado
    except Exception as exc:  # ante error del modelo, se degrada al respaldo
        _breaker_gemini.registrar_fallo()
        log.warning("Backend Gemini falló (%s) [circuito=%s]; se usa el respaldo.",
                    exc, _breaker_gemini.estado)
        salida = await _responder_fallback(pregunta, usuario_id)
        salida["backend"] = "fallback (gemini indisponible)"
        return salida


async def responder(pregunta: str, usuario_id: str | None = None,
                    session_id: str | None = None) -> dict:
    """Punto de entrada: aplica memoria conversacional, caché y registro de traza
    sobre el razonamiento del agente.

    La sesión de memoria es `session_id` si viene, o el usuario autenticado
    (así el chat recuerda el hilo por usuario sin que el front mande sesión).
    """
    sesion = session_id or usuario_id
    historial = await redis_store.cargar_historial(sesion)

    # La caché solo aplica a preguntas sueltas (sin contexto previo): una respuesta
    # que depende del hilo no se puede reutilizar entre conversaciones distintas.
    usar_cache = not historial
    if usar_cache:
        cacheado = await redis_store.cache_obtener(usuario_id, pregunta)
        if cacheado is not None:
            cacheado = {**cacheado, "backend": f"{cacheado.get('backend', '')} (cache)".strip()}
            await redis_store.guardar_turno(sesion, pregunta, cacheado.get("respuesta", ""))
            return cacheado

    resultado = await _responder_core(pregunta, usuario_id, historial)

    if usar_cache:
        await redis_store.cache_guardar(usuario_id, pregunta, resultado)
    await redis_store.guardar_turno(sesion, pregunta, resultado.get("respuesta", ""))
    await redis_store.registrar_traza({
        "session": sesion,
        "usuario_id": usuario_id,
        "pregunta": pregunta,
        "backend": resultado.get("backend"),
        "respuesta": resultado.get("respuesta"),
        "traza": resultado.get("traza", []),
    })
    return resultado
