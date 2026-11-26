"""Carga inicial de datos de demostración (idempotente).

Usa el mismo ejemplo continuo que los mockups (marca ShopIA) para que la demo
sea coherente entre el frontend diseñado y el backend real.
"""

from sqlalchemy import func, select

from .database import SessionLocal
from .models import Categoria, Producto


async def seed_if_empty() -> None:
    async with SessionLocal() as session:
        existentes = await session.scalar(select(func.count()).select_from(Producto))
        if existentes:
            return

        cats = {
            "audio": Categoria(nombre="Audio"),
            "perifericos": Categoria(nombre="Periféricos"),
            "wearables": Categoria(nombre="Wearables"),
            "computacion": Categoria(nombre="Computación"),
            "celulares": Categoria(nombre="Celulares"),
            "gaming": Categoria(nombre="Gaming"),
            "hogar": Categoria(nombre="Hogar inteligente"),
        }
        session.add_all(list(cats.values()))
        await session.flush()  # asigna los id de categoría

        def prod(nombre: str, descripcion: str, precio: float, cat: str) -> Producto:
            return Producto(nombre=nombre, descripcion=descripcion, precio=precio, categoria_id=cats[cat].id)

        session.add_all(
            [
                # --- Audio ---
                prod("Auriculares Aura Pro",
                     "Auriculares inalámbricos con cancelación activa de ruido y 30 h de batería.",
                     189999.00, "audio"),
                prod("Auriculares Aura Lite",
                     "Auriculares in-ear inalámbricos, livianos, con estuche de carga.",
                     74999.00, "audio"),
                prod("Parlante Aura Boom",
                     "Parlante portátil resistente al agua con 12 h de reproducción.",
                     99999.00, "audio"),
                # --- Periféricos ---
                prod("Teclado mecánico Nova K",
                     "Teclado mecánico retroiluminado, switches marrones, layout español.",
                     119999.00, "perifericos"),
                prod("Mouse Nova M",
                     "Mouse inalámbrico ergonómico de 16000 DPI con batería recargable.",
                     54999.00, "perifericos"),
                prod("Monitor Nova View 27",
                     "Monitor de 27'' QHD a 165 Hz, panel IPS de 1 ms, ideal para trabajo y juego.",
                     329999.00, "perifericos"),
                prod("Cámara web Nova Cam HD",
                     "Cámara web 1080p con enfoque automático y micrófono con reducción de ruido.",
                     44999.00, "perifericos"),
                # --- Wearables ---
                prod("Smartwatch Pulse S",
                     "Reloj inteligente con GPS, medición de ritmo cardíaco y sueño.",
                     149999.00, "wearables"),
                prod("Banda deportiva Pulse Band",
                     "Pulsera de actividad con oxímetro, 14 días de batería y resistencia al agua.",
                     39999.00, "wearables"),
                # --- Computación ---
                prod("Notebook Nova Book 14",
                     "Notebook de 14'', procesador de 8 núcleos, 16 GB de RAM y SSD de 512 GB.",
                     1299999.00, "computacion"),
                prod("Tablet Pulse Tab 11",
                     "Tablet de 11'' con pantalla 2K, lápiz incluido y 128 GB de almacenamiento.",
                     329999.00, "computacion"),
                # --- Celulares ---
                prod("Smartphone Pulse Phone X",
                     "Teléfono 5G con cámara triple de 50 MP, pantalla OLED de 120 Hz y 256 GB.",
                     899999.00, "celulares"),
                prod("Smartphone Pulse Phone Lite",
                     "Teléfono 5G con batería de 5000 mAh, pantalla de 6,6'' y 128 GB.",
                     449999.00, "celulares"),
                # --- Gaming ---
                prod("Auriculares gamer Aura GX",
                     "Auriculares gamer con sonido envolvente 7.1, micrófono desmontable y luces RGB.",
                     134999.00, "gaming"),
                prod("Joystick inalámbrico Nova Pad",
                     "Joystick inalámbrico con gatillos hápticos y batería recargable.",
                     69999.00, "gaming"),
                # --- Hogar inteligente ---
                prod("Parlante inteligente Aura Home",
                     "Parlante inteligente con asistente por voz y control de los dispositivos del hogar.",
                     84999.00, "hogar"),
            ]
        )
        await session.commit()
