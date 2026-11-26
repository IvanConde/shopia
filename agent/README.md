# agent/ — Agente conversacional MCP

Spike del componente de IA conversacional (riesgo alto por tecnología nueva, por
eso se tanteó temprano). Demuestra el patrón **agente ReAct ↔ MCP ↔ dominio**:
el agente razona una pregunta en lenguaje natural, invoca una **herramienta MCP**
por HTTP y responde con **datos reales** de los microservicios.

## Componentes

```
agent/
  mcp_server/      Servidor MCP de dominio (transporte streamable-http).
                   Publica 3 herramientas que hacen de fachada a los servicios:
                     · buscar_productos(consulta)         -> Catálogo
                     · consultar_estado_pedido(pedido_id) -> Pedidos
                     · historial_pedidos(usuario_id)      -> Pedidos
  agent_service/   API del agente (FastAPI). Descubre las herramientas del
                   servidor MCP (langchain-mcp-adapters) y las orquesta con un
                   grafo ReAct de LangGraph. Endpoint POST /chat -> respuesta +
                   traza de razonamiento (pensamiento → acción → observación).
```

> En el diseño de destino cada microservicio hospeda su propio servidor MCP; en
> este spike se concentran en un único servidor-fachada, suficiente para
> demostrar el patrón de punta a punta.

## Backend del modelo (LLM)

Seleccionable por entorno (`GEMINI_API_KEY` en `.env`):

- **`gemini`** — modelo real de Google Gemini (free tier) sobre el grafo ReAct.
  Es el modo objetivo. Se activa al cargar la clave.
- **`fallback`** — planificador determinista por reglas, activo cuando **no** hay
  clave. Ejercita las **mismas** herramientas MCP y expone la misma traza, para
  poder probar y demostrar el andamiaje sin credenciales ni costo.

### Activar Gemini (opcional, gratis)
1. Generar una API key en https://aistudio.google.com/apikey (free tier).
2. En `infra/.env` (el `.env` que lee docker compose): `GEMINI_API_KEY=<tu-clave>`
   (opcional `MODELO_GEMINI=gemini-flash-lite-latest`, que en el free tier tiene más
   cuota y menor latencia).
3. Reiniciar el servicio: `cd infra && docker compose up -d agente`.
4. Verificar: `curl localhost:8005/health` → `"backend":"gemini"`.

La clave va **solo** en `infra/.env` (git-ignorado); nunca en el código ni en el
compose. El free tier tiene **cuota diaria acotada por modelo**: si se agota, el agente
degrada solo al respaldo determinista (se ve en `/health` como `backend: fallback`).

## Probar

```bash
# Directo (puerto de dev):
curl -s -X POST http://localhost:8005/chat -H "Content-Type: application/json" \
  -d '{"mensaje":"como va mi pedido <UUID> ?"}'

# Por el gateway (requiere JWT, como toda ruta que toca datos del usuario):
curl -s -X POST http://localhost/api/agente/chat -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" -d '{"mensaje":"buscar auriculares"}'
```

Ver el recorrido completo en [`../docs/GUIA_DE_USO.md`](../docs/GUIA_DE_USO.md).
