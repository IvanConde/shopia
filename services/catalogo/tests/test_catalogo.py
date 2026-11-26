"""Pruebas de endpoints y seed del servicio Catálogo (sesión de BD simulada)."""

import asyncio

import pytest
from fastapi import HTTPException

from app import main, seed


class Result:
    def __init__(self, items): self._i = items
    def scalars(self): return self
    def all(self): return self._i


class FakeSession:
    def __init__(self, items=None, obj=None):
        self._items = items or []
        self._obj = obj
    async def execute(self, *a, **k): return Result(self._items)
    async def get(self, model, id): return self._obj


def test_health():
    assert asyncio.run(main.health())["service"] == "catalogo"


def test_listar_categorias():
    assert asyncio.run(main.listar_categorias(FakeSession([]))) == []


def test_buscar_sin_filtro():
    assert asyncio.run(main.buscar_productos(None, FakeSession([]))) == []


def test_buscar_con_filtro():
    assert asyncio.run(main.buscar_productos("aura", FakeSession([]))) == []


def test_detalle_no_encontrado():
    with pytest.raises(HTTPException):
        asyncio.run(main.detalle_producto("id", FakeSession(obj=None)))


def test_detalle_ok():
    obj = object()
    assert asyncio.run(main.detalle_producto("id", FakeSession(obj=obj))) is obj


def test_seed_inserta_si_vacio(monkeypatch):
    añadidos = []

    class S:
        async def scalar(self, *a): return 0
        def add_all(self, x): añadidos.extend(x)
        async def flush(self): pass
        async def commit(self): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(seed, "SessionLocal", lambda: S())
    asyncio.run(seed.seed_if_empty())
    assert añadidos  # categorías + productos sembrados


def test_seed_no_duplica(monkeypatch):
    class S:
        async def scalar(self, *a): return 6
        def add_all(self, x): raise AssertionError("no debería insertar con datos")
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    monkeypatch.setattr(seed, "SessionLocal", lambda: S())
    asyncio.run(seed.seed_if_empty())  # no inserta
