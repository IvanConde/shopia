# Banco de entrenamiento del detector de anomalías — datos reales

`transacciones_reales.csv` es el conjunto con el que el **modelo desplegado**
(Isolation Forest) se ajusta al arrancar el servicio. Son **transacciones reales
de e-commerce**, no sintéticas.

## Fuente
- **UCI ML Repository #352 — "Online Retail"** (Daqing Chen, 2015): minorista
  online real del Reino Unido, dic-2010 a dic-2011, **541.909 líneas de factura**.
  https://archive.ics.uci.edu/dataset/352/online+retail
- Licencia del dataset: uso académico/investigación. El `.xlsx` original (~23 MB)
  **no se versiona** en el repo (es dato de entrada); acá se guarda únicamente el
  derivado reducido con las tres señales del prototipo.

## Mapeo a las 3 señales del detector
A partir de las columnas reales:

| Señal del prototipo | Columna(s) de UCI |
|---|---|
| `monto` | `Quantity × UnitPrice` (total de línea), llevado a pesos (ver escala) |
| `items` | `Quantity` (valor real, sin alterar) |
| `hora`  | `InvoiceDate.hour` (valor real, sin alterar) |

## Preprocesamiento (reproducible, semilla 42)
1. **Legítimas:** se descartan cancelaciones (`InvoiceNo` que empieza con `C`),
   `Quantity ≤ 0` y `UnitPrice ≤ 0`, y filas con nulos → 530.104 transacciones.
2. **Escala monetaria £ → ARS:** factor lineal `K = mediana_precio_catálogo /
   mediana_monto_£ = 127.499 / 9,90 ≈ 12.879`. Solo convierte la *unidad*
   monetaria al nivel de precios del catálogo de ShopIA; **la forma de la
   distribución (correlaciones, franja horaria, cantidades) es la real**. `items`
   y `hora` no se reescalan.
3. **Dominio de consumo (B2C):** ShopIA es una tienda de consumo, no un mayorista.
   Se seleccionan las transacciones de escala de consumo —`items ≤ 8` y
   `monto ∈ [20.000, 2.000.000]` ARS, el rango operativo del catálogo— que son el
   **63 %** de las legítimas (335.616). No se recortan valores: se *seleccionan*
   filas dentro del dominio.
4. **Muestra:** 10.000 transacciones tomadas de forma determinista (semilla 42).

## Hiperparámetros del modelo (sin cambios)
`IsolationForest(n_estimators=100, contamination=0.02, random_state=42)` — los
mismos de siempre; lo único que cambió es **la fuente del `fit`** (sintético →
real).

## Verificación (banco controlado de 1000 transacciones, 5 % inyectado)
Con el modelo ajustado sobre estos datos reales: **TPR 100 %** (≥ 90 %) y
**FPR 3,47 %** (≤ 5 %). El dataset sintético se conserva solo como respaldo de
arranque y para **inyectar** las anomalías conocidas del banco de validación y de la demo.
