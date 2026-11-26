"""Pruebas del servicio de autenticación (emisión y validación de JWT).

Se invocan las corrutinas de los endpoints directamente (sin TestClient, que
requeriría httpx). Corre con asyncio.run.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response

from app import main
from app.main import LoginIn


def test_health():
    assert asyncio.run(main.health())["service"] == "auth"


def test_login_ok_devuelve_token():
    # El usuario demo se valida localmente, sin tocar Usuarios.
    r = asyncio.run(main.login(LoginIn(email="juan@shopia.demo", password="demo")))
    assert r["token_type"] == "bearer" and len(r["access_token"]) > 20


def test_login_password_incorrecta(monkeypatch):
    # Password mala del demo -> cae a Usuarios, que también la rechaza.
    monkeypatch.setattr(main, "_verificar_en_usuarios", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as e:
        asyncio.run(main.login(LoginIn(email="juan@shopia.demo", password="mala")))
    assert e.value.status_code == 401


def test_login_usuario_inexistente(monkeypatch):
    monkeypatch.setattr(main, "_verificar_en_usuarios", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        asyncio.run(main.login(LoginIn(email="nadie@shopia.demo", password="demo")))


def test_login_via_usuarios_ok(monkeypatch):
    # un usuario registrado (no demo) se valida contra el servicio de Usuarios.
    monkeypatch.setattr(main, "_verificar_en_usuarios",
                        AsyncMock(return_value={"user_id": "abc-123", "nombre": "Ana"}))
    r = asyncio.run(main.login(LoginIn(email="ana@shopia.demo", password="secreta")))
    assert r["token_type"] == "bearer" and len(r["access_token"]) > 20
    main._verificar_en_usuarios.assert_awaited_once()


def test_verify_sin_header():
    with pytest.raises(HTTPException):
        asyncio.run(main.verify(Response(), authorization=None))


def test_verify_esquema_no_bearer():
    with pytest.raises(HTTPException):
        asyncio.run(main.verify(Response(), authorization="Basic abc"))


def test_verify_token_invalido():
    with pytest.raises(HTTPException):
        asyncio.run(main.verify(Response(), authorization="Bearer no.es.jwt"))


def test_verify_ok_expone_headers():
    tok = asyncio.run(main.login(LoginIn(email="juan@shopia.demo", password="demo")))["access_token"]
    resp = Response()
    out = asyncio.run(main.verify(resp, authorization=f"Bearer {tok}"))
    assert out["ok"] is True
    assert resp.headers["X-User-Id"] == "11111111-1111-1111-1111-111111111111"
    assert resp.headers["X-User-Email"] == "juan@shopia.demo"
