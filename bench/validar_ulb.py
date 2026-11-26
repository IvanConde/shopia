"""Validación del detector de anomalías sobre un DATASET REAL y ETIQUETADO.

Dataset: ULB / Worldline "Credit Card Fraud Detection" (Kaggle
`mlg-ulb/creditcardfraud`). 284.807 transacciones reales con tarjeta (titulares
europeos, sep-2013), 492 fraudes (0,172 %). Columnas: Time, V1..V28 (features
anonimizadas por PCA), Amount y Class (etiqueta: 1=fraude, 0=legítima).

Objetivo: correr el **mismo** Isolation Forest del prototipo (no supervisado,
`n_estimators=100`, `random_state=42`) sobre datos **reales** y medir TPR/FPR,
precisión y AUC contra la etiqueta real (la etiqueta NO se usa para entrenar,
solo para evaluar). Es validación offline: no toca el servicio `anomalias`.

Uso (con el venv que tiene pandas/scikit-learn):
    python -I bench/validar_ulb.py <ruta/creditcard.csv>
"""

import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

SEMILLA = 42          # misma que el detector de producción
N_ESTIMATORS = 100    # misma que el detector de producción


def _metricas(y_real: np.ndarray, pred_anom: np.ndarray) -> dict:
    tp = int(((pred_anom == 1) & (y_real == 1)).sum())
    fn = int(((pred_anom == 0) & (y_real == 1)).sum())
    fp = int(((pred_anom == 1) & (y_real == 0)).sum())
    tn = int(((pred_anom == 0) & (y_real == 0)).sum())
    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "tpr": tpr, "fpr": fpr, "prec": prec}


def main(ruta_csv: str) -> None:
    df = pd.read_csv(ruta_csv)
    y = df["Class"].to_numpy().astype(int)
    X = df.drop(columns=["Class"]).to_numpy(dtype=float)  # Time, V1..V28, Amount
    # Time y Amount están en escalas muy distintas de las V (ya ~estandarizadas
    # por PCA): se estandariza todo para que ninguna variable domine por escala.
    X = StandardScaler().fit_transform(X)

    n = len(y)
    n_fraude = int(y.sum())
    tasa_real = n_fraude / n

    print("=" * 79)
    print("VALIDACIÓN CON DATASET REAL — ULB Credit Card Fraud (real + etiquetado)")
    print("=" * 79)
    print(f"Fuente: Kaggle mlg-ulb/creditcardfraud | {n} transacciones reales, "
          f"{n_fraude} fraudes ({tasa_real*100:.3f} %)")
    print(f"Features usadas: Time + V1..V28 + Amount ({X.shape[1]} columnas), estandarizadas")
    print(f"Modelo: IsolationForest(n_estimators={N_ESTIMATORS}, random_state={SEMILLA}) — NO supervisado")
    print("La etiqueta Class NO entra al modelo; solo se usa para medir.\n")

    # Puntajes de anomalía independientes del umbral (cuanto más alto, más anómalo).
    # Se entrena una vez con contamination='auto' para obtener score_samples; las
    # métricas de ranking (AUC) no dependen del umbral elegido.
    base = IsolationForest(n_estimators=N_ESTIMATORS, random_state=SEMILLA, contamination="auto")
    base.fit(X)
    score = -base.score_samples(X)  # mayor = más anómalo
    roc = roc_auc_score(y, score)
    pr = average_precision_score(y, score)
    print(f"Capacidad de ranking (independiente del umbral): ROC-AUC = {roc:.3f} | "
          f"PR-AUC (avg precision) = {pr:.3f}")
    print(f"(base de PR-AUC si fuera azar = tasa de fraude = {tasa_real:.5f})\n")

    # Matriz de confusión a distintos umbrales (contamination). El primero iguala la
    # tasa real de fraude; los otros son los que usa el prototipo (2 %) y un punto
    # intermedio, para ver la sensibilidad al umbral.
    print(f"{'contamination':>14} | {'TP':>4} {'FN':>4} {'FP':>6} {'TN':>7} | "
          f"{'TPR(recall)':>11} {'FPR':>7} {'precisión':>9}")
    print("-" * 79)
    for cont in (round(tasa_real, 5), 0.005, 0.02):
        modelo = IsolationForest(n_estimators=N_ESTIMATORS, random_state=SEMILLA, contamination=cont)
        modelo.fit(X)
        pred = (modelo.predict(X) == -1).astype(int)
        m = _metricas(y, pred)
        etiqueta = f"{cont:.5f}" + (" (real)" if abs(cont - tasa_real) < 1e-4 else "")
        print(f"{etiqueta:>14} | {m['tp']:>4} {m['fn']:>4} {m['fp']:>6} {m['tn']:>7} | "
              f"{m['tpr']*100:>10.1f}% {m['fpr']*100:>6.2f}% {m['prec']*100:>8.1f}%")

    # Precisión en el top-N del ranking de anomalía (lift sobre el azar): de las N
    # transacciones MÁS anómalas según el modelo, cuántas son fraude real. Es la lectura
    # más intuitiva para datos muy desbalanceados (mejor que la precisión a un umbral fijo).
    orden = np.argsort(score)[::-1]  # de más a menos anómala
    print("\nPrecisión en el top-N del ranking (lift sobre el azar):")
    print(f"{'top-N':>8} | {'fraudes':>7} | {'precisión@N':>11} {'recall@N':>9} {'lift':>6}")
    print("-" * 55)
    for k in (100, 492, 1000, 2000, 5000):
        top = orden[:k]
        fr = int(y[top].sum())
        prec_k = fr / k
        rec_k = fr / n_fraude
        lift = prec_k / tasa_real
        print(f"{k:>8} | {fr:>7} | {prec_k*100:>10.1f}% {rec_k*100:>8.1f}% {lift:>5.0f}x")

    print("\nLectura honesta:")
    print("- Isolation Forest NO supervisado sobre datos reales etiquetados: detecta una")
    print("  fracción relevante del fraude sin haber visto etiquetas, pero con precisión")
    print("  modesta (el fraude está muy solapado con lo legítimo en el espacio PCA).")
    print("- El AUC resume la capacidad de *ranking* sin fijar umbral; la matriz muestra el")
    print("  compromiso TPR/FPR al elegirlo. El punto no es ganar el benchmark, sino dejar")
    print("  'validado sobre datos reales etiquetados', cerrando la objeción del dataset sintético.")


if __name__ == "__main__":
    try:  # salida UTF-8 aunque la consola sea cp1252 (y aunque -I ignore PYTHONUTF8)
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ruta = sys.argv[1] if len(sys.argv) > 1 else "creditcard.csv"
    main(ruta)
