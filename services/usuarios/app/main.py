import logging
import uuid
from contextlib import asynccontextmanager

import bcrypt
from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .config import settings
from .database import Base, engine, get_session
from .events import cerrar_conexion, publicar_evento

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Usuario demo, coherente con el sembrado en el servicio auth (mismo id y email).
_DEMO = {
    "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "email": "juan@shopia.demo",
    "nombre": "Juan Pérez",
    "segmento": "recurrente",
}


def _hash(clave: str) -> str:
    # Hash fuerte con bcrypt: incorpora un salt aleatorio por contraseña y es
    # deliberadamente lento (resistente a fuerza bruta / tablas rainbow).
    # Reemplaza al sha256 sin sal de versiones previas.
    return bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode()


def _verificar(clave: str, hash_almacenado: str) -> bool:
    # bcrypt guarda el salt dentro del propio hash, por lo que la comparación es
    # por checkpw y no por igualdad (dos hashes de la misma clave difieren). Si el
    # hash almacenado no tiene formato bcrypt (p. ej. un sha256 heredado), checkpw
    # lanza y se trata como credencial inválida.
    try:
        return bcrypt.checkpw(clave.encode(), hash_almacenado.encode())
    except (ValueError, TypeError):
        return False


async def _sembrar_demo() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migración ligera: agrega canal_preferido a la tabla ya existente.
        await conn.execute(text(
            f"ALTER TABLE {settings.db_schema}.usuario "
            "ADD COLUMN IF NOT EXISTS canal_preferido VARCHAR(20) NOT NULL DEFAULT 'email'"
        ))
    async for session in get_session():
        existe = await session.get(models.Usuario, _DEMO["id"])
        if existe is None:
            session.add(
                models.Usuario(
                    id=_DEMO["id"], email=_DEMO["email"], nombre=_DEMO["nombre"],
                    hash_password=_hash("demo"), rol="comprador", segmento=_DEMO["segmento"],
                )
            )
            await session.commit()
        elif not existe.hash_password.startswith("$2"):
            # Migra el hash del demo de sha256 (versiones previas) a bcrypt sobre
            # el volumen ya existente, para que el formato quede uniforme.
            existe.hash_password = _hash("demo")
            await session.commit()
        break


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _sembrar_demo()
    yield
    await cerrar_conexion()


app = FastAPI(title="Usuarios — ShopIA", version="0.1.0", lifespan=lifespan)


class PerfilOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre: str
    rol: str
    segmento: str
    canal_preferido: str


class PerfilUpdate(BaseModel):
    nombre: str | None = None
    segmento: str | None = None
    canal_preferido: str | None = None


class RegistroIn(BaseModel):
    email: str
    nombre: str
    password: str
    segmento: str = "nuevo"
    canal_preferido: str = "email"


class CredencialesIn(BaseModel):
    email: str
    password: str


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "usuarios"}


@app.post("/usuarios", response_model=PerfilOut, status_code=201, tags=["usuarios"])
async def registrar(body: RegistroIn, session: AsyncSession = Depends(get_session)):
    """Alta de un usuario. Ruta pública: un visitante crea su
    cuenta antes de tener token. La contraseña se guarda hasheada (nunca en claro).
    """
    existe = (
        await session.execute(
            select(models.Usuario).where(models.Usuario.email == body.email.lower())
        )
    ).scalar_one_or_none()
    if existe is not None:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")

    usuario = models.Usuario(
        email=body.email.lower(), nombre=body.nombre, hash_password=_hash(body.password),
        rol="comprador", segmento=body.segmento, canal_preferido=body.canal_preferido,
    )
    session.add(usuario)
    await session.commit()
    await session.refresh(usuario)
    return usuario


@app.post("/usuarios/verificar", tags=["usuarios"])
async def verificar_credenciales(body: CredencialesIn, session: AsyncSession = Depends(get_session)):
    """Verificación de credenciales para el servicio de autenticación (uso interno:
    no se publica en el gateway). Devuelve los datos del usuario o 401."""
    usuario = (
        await session.execute(
            select(models.Usuario).where(models.Usuario.email == body.email.lower())
        )
    ).scalar_one_or_none()
    if usuario is None or not _verificar(body.password, usuario.hash_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return {"user_id": str(usuario.id), "email": usuario.email, "nombre": usuario.nombre}


@app.get("/usuarios", response_model=list[PerfilOut], tags=["usuarios"])
async def listar(session: AsyncSession = Depends(get_session)):
    filas = (await session.execute(select(models.Usuario))).scalars().all()
    return filas


@app.get("/usuarios/{usuario_id}", response_model=PerfilOut, tags=["usuarios"])
async def obtener(usuario_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    usuario = await session.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


@app.patch("/usuarios/{usuario_id}", response_model=PerfilOut, tags=["usuarios"])
async def actualizar(
    usuario_id: uuid.UUID, body: PerfilUpdate, session: AsyncSession = Depends(get_session)
):
    usuario = await session.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if body.nombre is not None:
        usuario.nombre = body.nombre
    if body.segmento is not None:
        usuario.segmento = body.segmento
    if body.canal_preferido is not None:
        usuario.canal_preferido = body.canal_preferido
    await session.commit()
    await session.refresh(usuario)

    # Evento de dominio: otros servicios (p. ej. Notificaciones) pueden reaccionar.
    await publicar_evento(
        "usuarios.actualizados",
        {"usuario_id": str(usuario.id), "nombre": usuario.nombre, "segmento": usuario.segmento},
    )
    return usuario


@app.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["usuarios"])
async def eliminar(
    usuario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    """Baja de cuenta — derecho de supresión (Art. 16 Ley 25.326).

    El titular solo puede dar de baja su propia cuenta: si la petición viene
    autenticada por el gateway, el `X-User-Id` del JWT debe coincidir con el id a
    eliminar. Se borra el registro del servicio dueño de la PII (Usuarios) y se
    publica `usuarios.eliminados` para que el resto anonimice sus copias en
    cascada; los pedidos se conservan (obligación contable) pero quedan sin datos
    personales asociados.
    """
    if x_user_id and x_user_id != str(usuario_id):
        raise HTTPException(status_code=403, detail="Solo se puede dar de baja la propia cuenta")

    usuario = await session.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    await session.delete(usuario)
    await session.commit()

    await publicar_evento("usuarios.eliminados", {"usuario_id": str(usuario_id)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
