"""Pruebas funcionales de los tres módulos de IA (agente, anomalías, notificaciones)."""

import time

import httpx

from conftest import ANOMALIAS, NOTIFICACIONES, crear_pedido, esperar_estado_final


def test_agente_responde_con_traza(cliente, headers):
    """El agente responde una búsqueda y expone su backend y traza."""
    r = cliente.post("/api/agente/chat", headers=headers, json={"mensaje": "quiero auriculares aura"})
    assert r.status_code == 200
    datos = r.json()
    assert datos.get("respuesta"), "el agente no devolvió respuesta"
    assert datos.get("backend") in ("gemini", "fallback", "fallback (gemini indisponible)")
    assert isinstance(datos.get("traza"), list)


def test_deteccion_de_anomalia(cliente, headers, producto):
    """Un pedido de monto atípicamente alto genera una alerta de fraude."""
    antes = len(httpx.get(f"{ANOMALIAS}/alertas", timeout=10).json())

    # Cantidad grande -> monto muy por encima del patrón normal -> anomalía.
    crear_pedido(cliente, headers, producto["id"], cantidad=500)

    alertas = []
    fin = time.time() + 8
    while time.time() < fin:
        alertas = httpx.get(f"{ANOMALIAS}/alertas", timeout=10).json()
        if len(alertas) > antes:
            break
        time.sleep(0.4)
    assert len(alertas) > antes, "no se generó la alerta de fraude esperada"
    assert alertas[0]["score"] < 0  # score negativo = transacción aislada/anómala


def test_notificacion_adaptativa(cliente, headers, producto):
    """Un pago resuelto genera una notificación con backend y texto válidos."""
    antes = httpx.get(f"{NOTIFICACIONES}/health", timeout=10).json()["notificaciones_enviadas"]

    pedido = crear_pedido(cliente, headers, producto["id"])
    esperar_estado_final(cliente, headers, pedido["id"])

    notifs = []
    fin = time.time() + 8
    while time.time() < fin:
        salud = httpx.get(f"{NOTIFICACIONES}/health", timeout=10).json()
        if salud["notificaciones_enviadas"] > antes:
            notifs = httpx.get(f"{NOTIFICACIONES}/notificaciones", params={"limit": 1}, timeout=10).json()
            break
        time.sleep(0.4)
    assert notifs, "no se generó la notificación esperada"
    n = notifs[0]
    assert n["backend"] in ("gemini", "cache", "fallback")
    assert n["mensaje"].strip()
    assert n["asunto"].strip()
