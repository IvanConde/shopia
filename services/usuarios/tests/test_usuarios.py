"""Pruebas de endpoints, hash y eventos del servicio Usuarios (BD simulada)."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app import events, main
from app.main import CredencialesIn, PerfilUpdate, RegistroIn


class Result:
    def __init__(self, items): self._i = items
    def scalars(self): return self
    def all(self): return self._i
    def scalar_one_or_none(self): return self._i[0] if self._i else None


class FakeSession:
    def __init__(self, items=None, obj=None):
        self._items = items or []
        self._obj = obj
        self.eliminado = None
    def add(self, o): pass
    async def execute(self, *a, **k): return Result(self._items)
    async def get(self, model, id): return self._obj
    async def commit(self): pass
    async def refresh(self, o): pass
    async def delete(self, o): self.eliminado = o


def test_hash_es_bcrypt_y_verifica():
    h = main._hash("demo")
    assert h.startswith("$2")          # formato bcrypt
    assert h != main._hash("demo")     # salt aleatorio => distinto cada vez
    assert main._verificar("demo", h)  # checkpw valida la clave correcta
    assert not main._verificar("mala", h)
    assert not main._verificar("demo", "hash-invalido")  # hash heredado/corrupto no revienta


def test_health():
    assert asyncio.run(main.health())["service"] == "usuarios"


def test_listar():
    assert asyncio.run(main.listar(FakeSession([]))) == []


def test_obtener_404():
    with pytest.raises(HTTPException):
        asyncio.run(main.obtener("id", FakeSession(obj=None)))


def test_obtener_ok():
    u = object()
    assert asyncio.run(main.obtener("id", FakeSession(obj=u))) is u


def test_actualizar_publica_evento(monkeypatch):
    monkeypatch.setattr(main, "publicar_evento", AsyncMock())
    usuario = SimpleNamespace(id="11111111-1111-1111-1111-111111111111", nombre="Juan", segmento="nuevo")
    out = asyncio.run(main.actualizar("id", PerfilUpdate(nombre="Juana", segmento="vip"),
                                      FakeSession(obj=usuario)))
    assert out.nombre == "Juana" and out.segmento == "vip"
    main.publicar_evento.assert_awaited()


def test_actualizar_404(monkeypatch):
    monkeypatch.setattr(main, "publicar_evento", AsyncMock())
    with pytest.raises(HTTPException):
        asyncio.run(main.actualizar("id", PerfilUpdate(nombre="x"), FakeSession(obj=None)))


def test_registrar_ok():
    # alta de un usuario nuevo (email no existente).
    out = asyncio.run(main.registrar(
        RegistroIn(email="Ana@Shopia.Demo", nombre="Ana", password="secreta"),
        FakeSession(items=[])))
    assert out.email == "ana@shopia.demo" and out.nombre == "Ana"
    assert out.hash_password != "secreta"               # nunca en claro
    assert main._verificar("secreta", out.hash_password)  # se guarda hasheada (bcrypt)


def test_registrar_duplicado_409():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.registrar(
            RegistroIn(email="ana@shopia.demo", nombre="x", password="y"),
            FakeSession(items=[object()])))
    assert exc.value.status_code == 409


def test_verificar_ok():
    u = SimpleNamespace(id="abc", email="ana@shopia.demo", nombre="Ana",
                        hash_password=main._hash("secreta"))
    out = asyncio.run(main.verificar_credenciales(
        CredencialesIn(email="ana@shopia.demo", password="secreta"), FakeSession(items=[u])))
    assert out["user_id"] == "abc" and out["nombre"] == "Ana"


def test_verificar_password_incorrecta_401():
    u = SimpleNamespace(id="abc", email="ana@shopia.demo", nombre="Ana",
                        hash_password=main._hash("secreta"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.verificar_credenciales(
            CredencialesIn(email="ana@shopia.demo", password="MALA"), FakeSession(items=[u])))
    assert exc.value.status_code == 401


def test_verificar_inexistente_401():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.verificar_credenciales(
            CredencialesIn(email="nadie@shopia.demo", password="x"), FakeSession(items=[])))
    assert exc.value.status_code == 401


def test_eliminar_ok_publica_evento(monkeypatch):
    # baja de cuenta -> borra el registro y publica usuarios.eliminados.
    monkeypatch.setattr(main, "publicar_evento", AsyncMock())
    uid = "11111111-1111-1111-1111-111111111111"
    usuario = SimpleNamespace(id=uid)
    sesion = FakeSession(obj=usuario)
    resp = asyncio.run(main.eliminar(uid, sesion, x_user_id=uid))
    assert resp.status_code == 204
    assert sesion.eliminado is usuario
    main.publicar_evento.assert_awaited()


def test_eliminar_ajeno_403(monkeypatch):
    monkeypatch.setattr(main, "publicar_evento", AsyncMock())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.eliminar("11111111-1111-1111-1111-111111111111",
                                  FakeSession(obj=object()),
                                  x_user_id="22222222-2222-2222-2222-222222222222"))
    assert exc.value.status_code == 403


def test_eliminar_404(monkeypatch):
    monkeypatch.setattr(main, "publicar_evento", AsyncMock())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.eliminar("11111111-1111-1111-1111-111111111111",
                                  FakeSession(obj=None), x_user_id=None))
    assert exc.value.status_code == 404


def test_publicar_evento_ok_y_degrada(monkeypatch):
    exch = AsyncMock(); chan = AsyncMock(); chan.declare_exchange.return_value = exch
    conn = AsyncMock(); conn.channel.return_value = chan

    async def ok(url): return conn
    monkeypatch.setattr(events.aio_pika, "connect_robust", ok)
    assert asyncio.run(events.publicar_evento("usuarios.actualizados", {"a": 1})) is True
    asyncio.run(events.cerrar_conexion())

    async def boom(url): raise RuntimeError("sin bus")
    monkeypatch.setattr(events.aio_pika, "connect_robust", boom)
    assert asyncio.run(events.publicar_evento("usuarios.actualizados", {})) is False
