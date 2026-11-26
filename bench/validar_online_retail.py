"""Validación del detector de anomalías sobre un DATASET REAL de E-COMMERCE.

Dataset: UCI ML Repository "Online Retail" (Daqing Chen, 2015) — minorista online
real del Reino Unido (dic-2010 a dic-2011), ~541.909 filas. No está etiquetado para
fraude (es no supervisado puro, justo lo que hace Isolation Forest), pero mapea
**exactamente** a las 3 features del prototipo:
    Quantity              -> cantidad de ítems
    Quantity * UnitPrice  -> monto (total de la línea)
    InvoiceDate.hour      -> hora del día

Al no haber etiqueta de fraude, se evalúa con **proxies de anomalía** operativos:
facturas de cancelación (InvoiceNo que empieza con 'C'), cantidades <= 0 y precios
<= 0 (devoluciones/errores/registros inválidos). Se mide qué fracción de esos casos
"anómalos" reales marca el detector. Es validación offline: no toca `anomalias`.

Uso (con el venv que tiene pandas/scikit-learn/openpyxl):
    python -I bench/validar_online_retail.py <ruta/online_retail.zip>
"""

import sys
import zipfile

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

SEMILLA = 42
N_ESTIMATORS = 100


def _leer(ruta: str) -> pd.DataFrame:
    if ruta.lower().endswith(".zip"):
        with zipfile.ZipFile(ruta) as zf:
            nombre = next(n for n in zf.namelist() if n.lower().endswith((".xlsx", ".csv")))
            with zf.open(nombre) as fh:
                if nombre.lower().endswith(".csv"):
                    return pd.read_csv(fh, encoding="latin-1")
                return pd.read_excel(fh, engine="openpyxl")
    if ruta.lower().endswith(".csv"):
        return pd.read_csv(ruta, encoding="latin-1")
    return pd.read_excel(ruta, engine="openpyxl")


def main(ruta: str) -> None:
    df = _leer(ruta)
    df = df.dropna(subset=["Quantity", "UnitPrice", "InvoiceDate", "InvoiceNo"]).copy()

    # Nuestras 3 features, calculadas desde las columnas reales.
    df["InvoiceNo"] = df["InvoiceNo"].astype(str)
    monto = (df["Quantity"] * df["UnitPrice"]).to_numpy(dtype=float)
    items = df["Quantity"].to_numpy(dtype=float)
    hora = pd.to_datetime(df["InvoiceDate"]).dt.hour.to_numpy(dtype=float)
    X = np.column_stack([monto, items, hora])

    # Proxies de anomalía (no hay etiqueta de fraude real): cancelaciones, cantidades
    # no positivas y precios no positivos = transacciones operativamente inválidas.
    es_cancel = df["InvoiceNo"].str.startswith("C").to_numpy()
    cant_no_pos = (df["Quantity"] <= 0).to_numpy()
    precio_no_pos = (df["UnitPrice"] <= 0).to_numpy()
    proxy = (es_cancel | cant_no_pos | precio_no_pos).astype(int)

    n = len(df)
    n_proxy = int(proxy.sum())
    tasa_proxy = n_proxy / n

    Xs = StandardScaler().fit_transform(X)

    print("=" * 79)
    print("VALIDACIÓN CON DATASET REAL — UCI Online Retail (e-commerce real, sin etiqueta)")
    print("=" * 79)
    print(f"Fuente: UCI ML Repository #352 'Online Retail' | {n} líneas de factura reales")
    print("Features (mapeo 1:1 con el prototipo): [monto = Quantity*UnitPrice, "
          "ítems = Quantity, hora = InvoiceDate.hour]")
    print(f"Proxies de anomalía: cancelaciones (InvoiceNo 'C') + Quantity<=0 + UnitPrice<=0 "
          f"= {n_proxy} ({tasa_proxy*100:.2f} %)")
    print(f"  - cancelaciones: {int(es_cancel.sum())} | cantidad<=0: {int(cant_no_pos.sum())} | "
          f"precio<=0: {int(precio_no_pos.sum())}")
    print(f"Modelo: IsolationForest(n_estimators={N_ESTIMATORS}, random_state={SEMILLA}) — NO supervisado\n")

    print(f"{'contamination':>14} | {'detecta proxy':>13} | {'cobertura(TPR)':>14} {'FPR':>7}")
    print("-" * 79)
    for cont in (round(tasa_proxy, 4), 0.02):
        modelo = IsolationForest(n_estimators=N_ESTIMATORS, random_state=SEMILLA, contamination=cont)
        pred = (modelo.fit_predict(Xs) == -1).astype(int)
        tp = int(((pred == 1) & (proxy == 1)).sum())
        fn = int(((pred == 0) & (proxy == 1)).sum())
        fp = int(((pred == 1) & (proxy == 0)).sum())
        tn = int(((pred == 0) & (proxy == 0)).sum())
        tpr = tp / (tp + fn) if (tp + fn) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        etiqueta = f"{cont:.4f}" + (" (≈proxy)" if abs(cont - tasa_proxy) < 1e-3 else "")
        print(f"{etiqueta:>14} | {tp:>6}/{n_proxy:<6} | {tpr*100:>12.1f}% {fpr*100:>6.2f}%")

    print("\nLectura honesta:")
    print("- El detector transfiere SIN cambios de diseño a e-commerce real: las 3 features")
    print("  (monto, ítems, hora) mapean 1:1 a este dataset.")
    print("- Con un umbral comparable, Isolation Forest marca sobre todo las transacciones de")
    print("  MAGNITUD extrema (compras mayoristas muy grandes), que NO coinciden con los proxies")
    print("  operativos (cancelaciones/devoluciones): la cobertura de proxies es BAJA (~2 %). Es")
    print("  esperable: tras estandarizar, los outliers dominantes son los montos altos, no las")
    print("  cancelaciones de monto chico (aunque sean negativas).")
    print("- Conclusión honesta: sin etiqueta de fraude, 'anomalía' la define la distribución de")
    print("  las features (tamaño inusual), no una verdad de fraude. Esto refuerza por qué hace")
    print("  falta el dataset ETIQUETADO (ULB) para medir desempeño de fraude real, y por qué en")
    print("  el prototipo el detector es UNA capa de señal, no un veredicto único.")


if __name__ == "__main__":
    try:  # salida UTF-8 aunque la consola sea cp1252 (y aunque -I ignore PYTHONUTF8)
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ruta = sys.argv[1] if len(sys.argv) > 1 else "online_retail.zip"
    main(ruta)
