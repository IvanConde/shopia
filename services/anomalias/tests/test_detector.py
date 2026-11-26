"""Pruebas unitarias del detector de anomalías (Isolation Forest).

Ejercitan la lógica de puntuación de forma aislada, sin bus ni base de datos.
Correr en el entorno del servicio (tiene numpy/scikit-learn). Ver tests/README.md.
"""

from pathlib import Path

import numpy as np
import pytest

import app.detector as detector
from app.detector import entrenar, evaluar


@pytest.fixture(autouse=True)
def modelo_entrenado():
    entrenar()
    yield


def test_monto_normal_no_es_anomalia():
    es_anomalia, score = evaluar(75_000)
    assert es_anomalia is False
    assert score > 0  # dentro del patrón aprendido


def test_monto_atipicamente_alto_es_anomalia():
    es_anomalia, score = evaluar(7_500_000)
    assert es_anomalia is True
    assert score < 0  # transacción aislada


def test_score_decrece_con_montos_mas_extremos():
    _, score_normal = evaluar(120_000)
    _, score_extremo = evaluar(10_000_000)
    assert score_extremo < score_normal


def test_muchos_items_reduce_el_score():
    # (modelo ajustado sobre datos reales): el detector está dirigido por el
    # monto (como el fraude real); la cantidad de ítems es una señal secundaria que
    # BAJA el score aunque, con un monto normal, no cruce el umbral binario por sí
    # sola. Se verifica que más ítems reduzcan el score (aporte multivariado).
    _, score_pocos = evaluar(90_000, cantidad_items=1, hora=14)
    _, score_muchos = evaluar(90_000, cantidad_items=50, hora=14)
    assert score_muchos < score_pocos


def test_monto_alto_con_muchos_items_es_anomalia():
    # Combinación realista de fraude (monto elevado + muchos ítems), como la que
    # inyecta la demo: sí cruza el umbral.
    es_anomalia, score = evaluar(5_000_000, cantidad_items=50, hora=3)
    assert es_anomalia is True
    assert score < 0


def test_hora_atipica_reduce_el_score():
    # La misma compra a las 3 a.m. es más "rara" que a las 15 h: la hora es otra
    # señal secundaria que baja el score (sin cruzar el umbral sola con monto normal).
    _, score_madrugada = evaluar(120_000, cantidad_items=2, hora=3)
    _, score_tarde = evaluar(120_000, cantidad_items=2, hora=15)
    assert score_madrugada < score_tarde


def test_evaluar_sin_entrenar_falla():
    detector._modelo = None
    with pytest.raises(RuntimeError):
        evaluar(100_000)
    entrenar()  # se re-entrena para no afectar a otras pruebas


# --- Respaldo sintético: el servicio no debe quedar sin modelo si falta el banco real ---

def test_cargar_datos_reales_sin_archivo(monkeypatch):
    # Si el banco real no existe, _cargar_datos_reales devuelve None (no rompe).
    monkeypatch.setattr(detector, "_RUTA_DATOS", Path("no_existe_banco_real.csv"))
    assert detector._cargar_datos_reales() is None


def test_cargar_datos_reales_formato_invalido(monkeypatch, tmp_path):
    # Un CSV con un número de columnas distinto de 3 se rechaza (devuelve None).
    malo = tmp_path / "malformado.csv"
    malo.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    monkeypatch.setattr(detector, "_RUTA_DATOS", malo)
    assert detector._cargar_datos_reales() is None


def test_entrenar_cae_al_sintetico_si_falta_el_banco(monkeypatch):
    # Sin banco real, entrenar() usa la muestra sintética de respaldo: el modelo
    # queda operativo y puntúa (monto atípico -> anomalía), para no bloquear el arranque.
    monkeypatch.setattr(detector, "_RUTA_DATOS", Path("no_existe_banco_real.csv"))
    detector._modelo = None
    entrenar()
    assert detector._modelo is not None
    es_anomalia, score = evaluar(7_500_000)
    assert es_anomalia is True
    assert score < 0


def test_muestra_sintetica_esquema():
    # La muestra de respaldo tiene el esquema [monto, ítems, hora] con rangos válidos.
    X = detector._muestra_sintetica(200, semilla=42)
    assert X.shape == (200, 3)
    assert np.all(X[:, 1] >= 1) and np.all(X[:, 1] <= 6)      # ítems 1..6
    assert np.all(X[:, 2] >= 0) and np.all(X[:, 2] <= 23)     # hora 0..23
