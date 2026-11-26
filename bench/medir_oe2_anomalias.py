"""Medición del detector de anomalías.

Genera una población sintética de transacciones (mayoría legítimas + 5 % de
anomalías inyectadas), la puntúa con el MISMO `detector` del servicio y calcula:
  * **TPR** (recall / tasa de detección): anomalías detectadas / anomalías reales.
  * **FPR** (falsos positivos): legítimas marcadas como anómalas / legítimas.
contra los umbrales objetivo: detección ≥ 90 %, falsos positivos ≤ 5 %.

Se corre DENTRO del contenedor `pfi-anomalias` (tiene numpy/scikit-learn y el
código del detector):
    docker cp bench/medir_oe2_anomalias.py pfi-anomalias:/srv/
    docker exec -w /srv pfi-anomalias python medir_oe2_anomalias.py
"""

from datetime import timedelta, timezone

import numpy as np

from app import detector

N = 1000
FRACCION_ANOMALIAS = 0.05
SEMILLA_EVAL = 2026  # distinta de la de entrenamiento, para no evaluar "en casa"

# Igual que pagos/consumer.py: Argentina es UTC-3 (sin horario de verano).
_TZ_AR = timezone(timedelta(hours=-3))


def _poblacion(n: int, semilla: int):
    """Devuelve (X, etiquetas) con `FRACCION_ANOMALIAS` de anomalías inyectadas.

    Las legítimas siguen el patrón del comercio (monto≈precio×ítems, horario
    diurno). Las anomalías son casos plausibles de fraude: monto muy alto,
    cantidad de ítems desmedida y/o compra en la madrugada.
    """
    rng = np.random.default_rng(semilla)
    n_anom = int(n * FRACCION_ANOMALIAS)
    n_norm = n - n_anom

    # Legítimas
    items = np.clip(1 + rng.poisson(0.9, n_norm), 1, 6)
    precio = rng.lognormal(np.log(90_000), 0.4, n_norm)
    monto = np.clip(precio * items, 20_000, 2_000_000)
    hora = np.clip(np.round(rng.normal(15, 3.5, n_norm)), 0, 23)
    X_norm = np.column_stack([monto, items, hora])
    y_norm = np.zeros(n_norm, dtype=int)

    # Anomalías (mezcla de tres tipos)
    filas = []
    for i in range(n_anom):
        tipo = i % 3
        if tipo == 0:   # monto desmedido
            filas.append([rng.uniform(5_000_000, 40_000_000), rng.integers(1, 4), rng.integers(9, 22)])
        elif tipo == 1:  # cantidad de ítems desmedida
            it = rng.integers(25, 120)
            filas.append([90_000 * it * rng.uniform(0.9, 1.1), it, rng.integers(9, 22)])
        else:            # compra en la madrugada con monto elevado
            filas.append([rng.uniform(800_000, 3_000_000), rng.integers(1, 5), rng.integers(1, 5)])
    X_anom = np.array(filas, dtype=float)
    y_anom = np.ones(n_anom, dtype=int)

    X = np.vstack([X_norm, X_anom])
    y = np.concatenate([y_norm, y_anom])
    orden = rng.permutation(len(y))
    return X[orden], y[orden]


def _validar_franja_horaria_pagos():
    """Cruce Pagos → detector en la hora del día.

    El detector aprende la franja horaria **local** de compra. Reproduce cómo
    Pagos emite la hora del evento: antes la tomaba en UTC, ahora en hora local
    (UTC-3). Una compra legítima de la tarde-noche local no debe marcarse anómala;
    con la hora en UTC esa misma compra caía en la "madrugada" que el modelo
    aprendió como atípica, inflando los falsos positivos reales.
    """
    # Compras legítimas de tarde-noche (hora local AR), monto e ítems normales.
    casos = [(90_000, 1, 18), (150_000, 1, 20), (75_000, 2, 21), (189_000, 1, 22), (120_000, 1, 23)]
    mal_utc = sum(detector.evaluar(m, it, (h - int(_TZ_AR.utcoffset(None).total_seconds() // 3600)) % 24)[0]
                  for m, it, h in casos)   # hora que habría emitido el bug (UTC = local + 3)
    mal_local = sum(detector.evaluar(m, it, h)[0] for m, it, h in casos)  # hora local (fix)

    print("\n=== Hora del evento de Pagos (UTC vs local AR) ===")
    print(f"Compras legítimas de tarde-noche (18-23 h local) evaluadas: {len(casos)}")
    print(f"  Marcadas anómalas con la hora en UTC (bug previo): {mal_utc}/{len(casos)}")
    print(f"  Marcadas anómalas con la hora local AR (fix):      {mal_local}/{len(casos)}")


def main():
    detector.entrenar()
    X, y = _poblacion(N, SEMILLA_EVAL)

    pred = np.array([1 if detector.evaluar(m, int(it), int(h))[0] else 0 for m, it, h in X])

    tp = int(((pred == 1) & (y == 1)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    print("=== Detección de anomalías (Isolation Forest, 3 features) ===")
    print(f"Población: {N} transacciones ({int(N*FRACCION_ANOMALIAS)} anómalas inyectadas, "
          f"{N-int(N*FRACCION_ANOMALIAS)} legítimas)")
    print(f"Matriz de confusión: TP={tp} FN={fn} FP={fp} TN={tn}")
    print(f"Tasa de detección (TPR/recall): {tpr*100:.1f} %   (objetivo ≥ 90 %)  "
          f"{'CUMPLE' if tpr >= 0.90 else 'NO CUMPLE'}")
    print(f"Falsos positivos (FPR):         {fpr*100:.1f} %   (objetivo ≤ 5 %)   "
          f"{'CUMPLE' if fpr <= 0.05 else 'NO CUMPLE'}")

    _validar_franja_horaria_pagos()


if __name__ == "__main__":
    main()
