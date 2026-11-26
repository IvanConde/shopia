"""Pruebas unitarias de los guardrails y utilidades del generador de notificaciones.

Lógica pura (sin LLM ni Redis). Correr en el entorno del servicio. Ver tests/README.md.
"""

from app.generador import _ESTADO_POR_RK, _aplicar_guardrails, _bucket, _fmt_monto


def test_rechaza_texto_vacio():
    ok, _, motivo = _aplicar_guardrails("   ")
    assert ok is False and motivo == "vacío"


def test_rechaza_texto_demasiado_largo():
    ok, _, _ = _aplicar_guardrails("x" * 601)
    assert ok is False


def test_rechaza_enlaces():
    ok, _, _ = _aplicar_guardrails("Ingresá a https://sitio-malicioso.test para cobrar")
    assert ok is False


def test_rechaza_arrobas():
    ok, _, _ = _aplicar_guardrails("Escribinos a soporte@shopia.demo")
    assert ok is False


def test_acepta_valido_y_agrega_marcadores_si_faltan():
    ok, texto, _ = _aplicar_guardrails("¡Tu pago fue aprobado con éxito!")
    assert ok is True
    assert "{pedido}" in texto and "{monto}" in texto  # se completan para personalizar


def test_acepta_conservando_marcadores_existentes():
    ok, texto, _ = _aplicar_guardrails("Pago del pedido {pedido} por ${monto} confirmado.")
    assert ok is True
    assert texto.count("{pedido}") == 1


def test_bucket_por_rango_de_monto():
    assert _bucket(50_000) == "bajo"
    assert _bucket(150_000) == "medio"
    assert _bucket(500_000) == "alto"


def test_formato_de_monto_local():
    assert _fmt_monto(74_999) == "74.999"
    assert _fmt_monto(1_000_000) == "1.000.000"


def test_estado_segun_routing_key():
    assert _ESTADO_POR_RK["pagos.completados"] == "aprobado"
    assert _ESTADO_POR_RK["pagos.rechazados"] == "rechazado"
    assert _ESTADO_POR_RK["pedidos.creados"] == "creado"
    assert _ESTADO_POR_RK["alertas.fraude"] == "fraude"
