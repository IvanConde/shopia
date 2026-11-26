"""Detector de anomalías transaccionales con Isolation Forest.

Modelo **no supervisado**: el modelo que corre en el prototipo se ajusta (`fit`)
sobre un conjunto de **transacciones reales de e-commerce** (UCI Online Retail,
minorista online del Reino Unido, 541.909 registros reales; ver
`datos/README.md`). De ese conjunto se usan las transacciones de escala de
**consumo** (dominio B2C de ShopIA) mapeadas a las tres señales del prototipo:

  * **monto** de la transacción (Quantity × UnitPrice, llevado a pesos por el
    ticket mediano del catálogo — ítems y hora son los valores reales);
  * **cantidad de ítems** del pedido (Quantity real);
  * **hora del día** (0–23) real de la factura.

Una vez entrenado, puntúa cada transacción entrante; las que quedan aisladas del
grueso de la distribución reciben un score negativo y se marcan como anómalas.
Ajustado sobre datos reales, el **monto es la señal de mayor peso**: la cantidad
de ítems y la hora, con un monto normal, bajan el score pero no cruzan el umbral
por sí solas; una combinación atípica (monto elevado junto a muchos ítems o una
hora inusual) sí puede elevarlo. El diseño admite sumar más señales (frecuencia
por usuario, dispositivo, geolocalización) cuando el evento las transporte.

Si el archivo de datos reales no estuviera disponible, se cae a una muestra
**sintética** equivalente (mismo esquema de 3 features) para no bloquear el
arranque; el camino normal es el de datos reales.
"""

import logging
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest

from .config import settings

logger = logging.getLogger("anomalias.detector")

_modelo: IsolationForest | None = None

# Hora "típica" por defecto cuando el evento no la transporta (mediodía/tarde).
_HORA_TIPICA = 14

# Ruta al banco de transacciones reales (relativa al paquete `app`).
_RUTA_DATOS = Path(__file__).resolve().parent / settings.datos_entrenamiento


def _cargar_datos_reales() -> np.ndarray | None:
    """Carga [monto, ítems, hora] del banco real (CSV con cabecera). None si falta."""
    if not _RUTA_DATOS.exists():
        return None
    datos = np.loadtxt(_RUTA_DATOS, delimiter=",", skiprows=1, dtype=float)
    if datos.ndim != 2 or datos.shape[1] != 3 or len(datos) == 0:
        logger.warning("Banco de datos reales con formato inesperado: %s", _RUTA_DATOS)
        return None
    return datos


def _muestra_sintetica(n: int, semilla: int) -> np.ndarray:
    """Fallback sintético con el mismo esquema: [monto, ítems, hora].

    El monto se construye como precio unitario (lognormal centrada en el rango del
    catálogo, ~$90k) por cantidad de ítems (1–6, mayoría 1–2), de modo que monto e
    ítems quedan correlacionados como en una compra real. La hora se concentra en
    la franja diurna/vespertina (pico ~15 h). Solo se usa si falta el banco real.
    """
    rng = np.random.default_rng(semilla)
    items = np.clip(1 + rng.poisson(0.9, size=n), 1, 6)
    precio_unitario = rng.lognormal(mean=np.log(90_000), sigma=0.4, size=n)
    montos = np.clip(precio_unitario * items, 20_000, 2_000_000)
    horas = np.clip(np.round(rng.normal(15, 3.5, size=n)), 0, 23)
    return np.column_stack([montos, items, horas])


def entrenar() -> None:
    """Entrena (una vez) el Isolation Forest sobre las transacciones reales.

    Fuente principal: banco real `datos/transacciones_reales.csv`. Si no estuviera,
    se usa la muestra sintética como respaldo (mismo esquema de 3 features).
    """
    global _modelo
    X = _cargar_datos_reales()
    if X is not None:
        fuente = f"datos reales (UCI Online Retail, {len(X)} transacciones)"
    else:
        X = _muestra_sintetica(settings.muestra_entrenamiento, settings.semilla)
        fuente = f"respaldo sintético ({len(X)} muestras)"
    modelo = IsolationForest(
        n_estimators=100,
        contamination=settings.contaminacion,
        random_state=settings.semilla,
    )
    modelo.fit(X)
    _modelo = modelo
    logger.info(
        "Isolation Forest entrenado: %s, 3 features (monto, ítems, hora), contamination=%s",
        fuente, settings.contaminacion,
    )


def evaluar(monto: float, cantidad_items: int = 1, hora: int | None = None) -> tuple[bool, float]:
    """Puntúa una transacción por sus características. Devuelve (es_anomalia, score).

    `score` es el `decision_function` del modelo: cuanto más negativo, más aislada
    (anómala) es respecto del patrón aprendido. `cantidad_items` y `hora` tienen
    valores por defecto típicos para poder puntuar con el monto solo.
    """
    if _modelo is None:
        raise RuntimeError("El detector no está entrenado; llamar a entrenar() primero.")
    h = _HORA_TIPICA if hora is None else int(hora)
    X = np.array([[float(monto), int(cantidad_items), h]])
    score = float(_modelo.decision_function(X)[0])
    es_anomalia = int(_modelo.predict(X)[0]) == -1
    return es_anomalia, score
