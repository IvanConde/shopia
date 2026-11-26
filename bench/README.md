# bench/ — Medición de objetivos

Scripts que miden, con números, dos objetivos específicos que antes estaban
«verificados funcionalmente»: imprimen los resultados medidos frente a sus umbrales objetivo.

## Detección de anomalías
`medir_oe2_anomalias.py`: genera 1000 transacciones sintéticas (5 % anomalías
inyectadas: monto desmedido, ítems desmedidos o compra de madrugada), las puntúa
con el `detector` del servicio y calcula TPR (detección) y FPR (falsos positivos).

Objetivos: detección ≥ 90 %, FP ≤ 5 %.

```bash
docker cp bench/medir_oe2_anomalias.py pfi-anomalias:/srv/
docker exec -w /srv pfi-anomalias python medir_oe2_anomalias.py
```

## Agente conversacional
`medir_oe3_agente.py`: lanza 20 consultas fijas (búsqueda, stock por id, estado de
pedido por id) al agente a través del gateway y mide el % que invoca la
herramienta MCP correcta (según la traza ReAct) y las latencias p50/p95/máx.

Objetivos: ≥ 90 % de consultas correctas, p95 < 5 s. Requiere el stack levantado y
`httpx`. Usa cuota del free tier de Gemini (~20 llamadas; incluye pausas de 1 s).

```bash
python bench/medir_oe3_agente.py # GATEWAY_URL opcional (def. http://127.0.0.1)
```

> En Windows, forzar UTF-8 en la salida: `PYTHONUTF8=1 python bench/medir_oe3_agente.py`.
