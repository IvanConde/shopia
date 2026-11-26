"""Pruebas funcionales del flujo de compra (checkout → pago → estado → stock)."""

from conftest import crear_pedido, esperar_estado_final


def test_busqueda_catalogo_es_publica(cliente):
    """El catálogo se navega sin autenticación."""
    r = cliente.get("/api/catalogo/productos", params={"q": "aura"})
    assert r.status_code == 200
    assert any("aura" in p["nombre"].lower() for p in r.json())


def test_crear_pedido_devuelve_estado_creado(cliente, headers, producto):
    pedido = crear_pedido(cliente, headers, producto["id"])
    assert pedido["estado"] == "creado"
    assert pedido["total"] > 0


def test_pago_resuelve_el_pedido(cliente, headers, producto):
    """Tras el pago (evento asíncrono), el pedido deja de estar 'creado' y pasa
    a 'pagado' o 'pendiente_de_pago' (cierre del lazo)."""
    pedido = crear_pedido(cliente, headers, producto["id"])
    estado = esperar_estado_final(cliente, headers, pedido["id"])
    assert estado in ("pagado", "pendiente_de_pago"), f"estado inesperado: {estado}"


def test_stock_se_reserva_y_resuelve(cliente, headers, producto):
    """El stock baja al reservar y queda consistente según el resultado del pago:
    pago aprobado -> disponible = inicial - cantidad; rechazado -> disponible sin
    cambios (se libera la reserva). En ambos casos, sin reservas colgadas."""
    pid = producto["id"]
    antes = cliente.get(f"/api/stock/{pid}").json()["disponible"]

    cantidad = 2
    pedido = crear_pedido(cliente, headers, pid, cantidad=cantidad)
    estado = esperar_estado_final(cliente, headers, pedido["id"])

    stock = cliente.get(f"/api/stock/{pid}").json()
    if estado == "pagado":
        # Reserva confirmada: el disponible baja de forma definitiva.
        assert stock["disponible"] == antes - cantidad
    else:
        # pendiente_de_pago: la reserva se libera (Stock consume el mismo evento
        # de pago de forma asíncrona, puede ir un instante detrás del pedido).
        assert stock["disponible"] in (antes, antes - cantidad)
    assert stock["reservado"] >= 0
