# F1 Pitstop Dashboard — Guía de Gráficos y Cálculos

> Documento técnico de referencia. Describe cada visualización y fórmula del dashboard, con ejemplos numéricos y propuestas de mejora.

---

## Índice

- [F1 Pitstop Dashboard — Guía de Gráficos y Cálculos](#f1-pitstop-dashboard--guía-de-gráficos-y-cálculos)
  - [Índice](#índice)
  - [1. Arquitectura de datos](#1-arquitectura-de-datos)
  - [2. Sesiones de práctica y su rol en la estrategia](#2-sesiones-de-práctica-y-su-rol-en-la-estrategia)
    - [2.1 ¿Qué sesiones se usan?](#21-qué-sesiones-se-usan)
    - [2.2 Flujo de carga de prácticas](#22-flujo-de-carga-de-prácticas)
    - [2.3 ¿Qué cálculos consumen los datos de práctica?](#23-qué-cálculos-consumen-los-datos-de-práctica)
    - [2.4 Ejemplo numérico: impacto del número de sesiones](#24-ejemplo-numérico-impacto-del-número-de-sesiones)
    - [2.5 ¿Qué pasa si no hay datos de práctica?](#25-qué-pasa-si-no-hay-datos-de-práctica)
    - [2.6 Columna `session` en los datos combinados](#26-columna-session-en-los-datos-combinados)
  - [3. Gráficos expuestos](#3-gráficos-expuestos)
    - [3.1 Tiempos de Vuelta](#31-tiempos-de-vuelta)
    - [3.2 Degradación de Neumáticos](#32-degradación-de-neumáticos)
    - [3.3 Temperatura Pista vs Aire](#33-temperatura-pista-vs-aire)
    - [3.4 Evolución Edad Neumático / Compuesto](#34-evolución-edad-neumático--compuesto)
    - [3.5 Análisis de Residuos](#35-análisis-de-residuos)
    - [3.6 Histograma de Tiempos de Vuelta](#36-histograma-de-tiempos-de-vuelta)
    - [3.7 Distribución por Compuesto (Boxplot)](#37-distribución-por-compuesto-boxplot)
    - [3.8 Consistencia — Coeficiente de Variación](#38-consistencia--coeficiente-de-variación)
  - [4. Cálculos del modelo de degradación](#4-cálculos-del-modelo-de-degradación)
    - [4.1 Modelo lineal simple (2 parámetros)](#41-modelo-lineal-simple-2-parámetros)
    - [4.2 Modelo con corrección de combustible (3 parámetros)](#42-modelo-con-corrección-de-combustible-3-parámetros)
    - [4.3 Modelo con temperatura de pista (4 parámetros)](#43-modelo-con-temperatura-de-pista-4-parámetros)
    - [4.4 Tiempo de stint](#44-tiempo-de-stint)
    - [4.5 Filtros de datos previos al ajuste](#45-filtros-de-datos-previos-al-ajuste)
  - [5. Métricas de calidad del modelo](#5-métricas-de-calidad-del-modelo)
    - [5.1 MAE (Error Absoluto Medio)](#51-mae-error-absoluto-medio)
    - [5.2 R² (Coeficiente de Determinación)](#52-r-coeficiente-de-determinación)
  - [6. Consistencia del piloto](#6-consistencia-del-piloto)
    - [6.1 Desviación estándar y CV](#61-desviación-estándar-y-cv)
  - [7. Planificador de estrategia](#7-planificador-de-estrategia)
    - [7.1 Enumeración de planes (DP + backtracking)](#71-enumeración-de-planes-dp--backtracking)
    - [7.2 Coste de pit stop](#72-coste-de-pit-stop)
    - [7.3 Restricción de dos compuestos](#73-restricción-de-dos-compuestos)
    - [7.4 Viabilidad por combustible](#74-viabilidad-por-combustible)
  - [8. Recomendación en vivo](#8-recomendación-en-vivo)
  - [9. Condiciones especiales](#9-condiciones-especiales)
    - [9.1 Safety Car](#91-safety-car)
    - [9.2 Lluvia](#92-lluvia)
    - [9.3 Simulador de impacto](#93-simulador-de-impacto)
  - [10. Detección de pit stops](#10-detección-de-pit-stops)
  - [11. Margen de mejora por área](#11-margen-de-mejora-por-área)
    - [11.1 Modelo de degradación](#111-modelo-de-degradación)
    - [11.2 Planificador de estrategia](#112-planificador-de-estrategia)
    - [11.3 Recomendación en vivo](#113-recomendación-en-vivo)
    - [11.4 Métricas y visualizaciones](#114-métricas-y-visualizaciones)
    - [11.5 Datos y pipeline](#115-datos-y-pipeline)

---

## 1. Arquitectura de datos

El pipeline de datos sigue este flujo:

```text
CSV exportado (logs_in/)
        ↓  load_session_csv()
    DataFrame raw
        ↓  detect_pit_events()  →  pit_stop / tire_change_pit
        ↓  build_lap_summary()
    lap_summary (1 fila = 1 vuelta)
        ↓  fit_degradation_model()  — excluye vueltas pit_stop=True
    models { compuesto → (a,b) | (a,b,c) | (a,b,c,d) }
        ↓  enumerate_plans()
    planes estratégicos ordenados por tiempo total
```

Columnas clave de `lap_summary`:

| Columna      | Descripción                                          |
| ------------ | ---------------------------------------------------- |
| `currentLap` | Número de vuelta                                     |
| `lap_time_s` | Tiempo de vuelta en segundos                         |
| `compound`   | Compuesto de neumático (`Soft`, `Medium`, `Hard`, …) |
| `tire_age`   | Vueltas acumuladas sobre ese neumático               |
| `fuel`       | Combustible estimado (kg)                            |
| `pit_stop`        | Booleano — vuelta con cualquier entrada a boxes        |
| `tire_change_pit` | Booleano — vuelta con cambio real de neumáticos        |
| `safety_car`      | Booleano — vuelta bajo safety car                      |
| `rain`            | Booleano — vuelta con lluvia                           |

---

## 2. Sesiones de práctica y su rol en la estrategia

### 2.1 ¿Qué sesiones se usan?

**Archivo**: `f1m/common.py` → `collect_practice_data()`

La función carga y combina automáticamente **todas** las sesiones de práctica disponibles para el circuito y piloto seleccionados. Las sesiones reconocidas son:

```python
PRACTICE_SESSION_NAMES = {
    "Practice 1",  # P1
    "Practice 2",  # P2
    "Practice 3",  # P3
    "Practice",    # genérico
    "FP1", "FP2", "FP3",  # nombres alternativos
}
```

La sesión de **Qualifying y Race quedan excluidas** de este conjunto de entrenamiento. Solo se usan como telemetría de la sesión activa en el dashboard principal.

---

### 2.2 Flujo de carga de prácticas

El sistema sigue un orden de prioridad: primero busca datos curados (Parquet), y si no existen, procesa los CSV originales.

```text
curated/
  track=Bahrain/
    session=Practice 1/
      driver=14_Fernando_Alonso/
        laps.parquet   ← leído primero (más rápido)
    session=Practice 2/
      driver=14_Fernando_Alonso/
        laps.parquet
    session=Practice 3/
      driver=14_Fernando_Alonso/
        laps.parquet
```

Si no hay Parquet, fallback a:

```text
logs_in/exported_data/Bahrain/Practice 1/<driver>/*.csv
```

**El resultado es un DataFrame unificado** con todas las vueltas de P1 + P2 + P3 concatenadas, con una columna `session` que indica el origen de cada vuelta.

---

### 2.3 ¿Qué cálculos consumen los datos de práctica?

| Cálculo                        | Función                           | Cómo usa las prácticas                                                                                                                                                                          |
| ------------------------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Modelo de degradación**      | `fit_degradation_model()`         | Ajusta la regresión OLS sobre todas las vueltas acumuladas de P1+P2+P3 para cada compuesto. Más sesiones = más puntos = mejor ajuste.                                                           |
| **Longitud máxima de stint**   | `max_stint_length()`              | Extrae el `tire_age` máximo observado en las prácticas. Si un piloto llegó a 22 vueltas con Medium en P2, el planificador sabrá que ese compuesto puede durar hasta 24 vueltas (`max_age + 2`). |
| **Combustible inicial (auto)** | `start_fuel` UI                   | Toma el `fuel` máximo registrado en los datos de práctica como estimación del combustible de inicio de carrera.                                                                                 |
| **Consumo por vuelta (auto)**  | `cons_per_lap` UI                 | Calcula la mediana de las diferencias consecutivas de `fuel` en las prácticas para estimar el consumo medio.                                                                                    |
| **Planificador de estrategia** | `enumerate_plans()`               | Usa `practice_laps` directamente para calcular `max_stint_length` por compuesto; los modelos vienen del ajuste sobre las prácticas.                                                             |
| **Recomendación en vivo**      | `live_pit_recommendation()`       | Usa los modelos ajustados en prácticas para proyectar el tiempo restante con cada compuesto alternativo.                                                                                        |
| **Consistencia del piloto**    | `calculate_consistency_metrics()` | Se calcula sobre la sesión activa (no sobre prácticas), pero puede verse sesgada si solo hay P1.                                                                                                |

---

### 2.4 Ejemplo numérico: impacto del número de sesiones

Supón que tenemos datos de **Fernando Alonso en Bahrain**, compuesto **Medium**:

| Sesión              | Vueltas válidas | tire_age máximo observado |
| ------------------- | --------------- | ------------------------- |
| Practice 1          | 8               | 8                         |
| Practice 2          | 12              | 15                        |
| Practice 3          | 10              | 11                        |
| **Total combinado** | **30**          | **15**                    |

**Con solo P1 (8 vueltas)**:

```text
a = 97.80,  b = 0.110   R² = 0.71  MAE = 0.38 s
```

**Con P1 + P2 + P3 (30 vueltas)**:

```text
a = 97.52,  b = 0.082   R² = 0.89  MAE = 0.21 s
```

El modelo con las tres prácticas tiene un R² **0.18 puntos mayor** y un MAE casi **a la mitad**. La pendiente de degradación baja de 0.11 a 0.082 s/vuelta porque P2 y P3 aportaron vueltas más representativas de un stint largo.

---

### 2.5 ¿Qué pasa si no hay datos de práctica?

Si `practice_data` está vacío, el tab de Estrategia muestra:
> "No hay datos suficientes para modelar."

**Excepción — Fallback de carrera**: En sesión de tipo Race, hay un checkbox opcional:
> "Sin prácticas. Usar vueltas iniciales de carrera como estimación provisoria"

Si se activa, se toman las **12 primeras vueltas de la carrera** como sustituto de práctica. El modelo resultante se marca como `(provisional)`. Este fallback es útil en directo cuando aún no se han procesado las prácticas, pero tiene limitaciones: las primeras vueltas de carrera tienen mayores niveles de combustible y posiblemente tráfico, lo que sesga la estimación de degradación.

---

### 2.6 Columna `session` en los datos combinados

Cada vuelta del DataFrame combinado lleva la etiqueta de su sesión de origen. El modelo la ignora en el ajuste OLS (solo usa `tire_age` y `lap_time_s`), pero está disponible para:

- Auditar qué sesiones aportaron datos (botón "Guardar modelo" incluye `sessions_used` en el JSON).
- Futuras mejoras como ponderar más las vueltas de P3 (más representativas de la carrera) que las de P1.

**Ejemplo de metadata guardada en `models/Bahrain/Fernando Alonso_model.json`**:

```json
{
  "models": { "Medium": [97.52, 0.082], "Hard": [98.10, 0.065] },
  "metadata": {
    "sessions_used": ["Practice 1", "Practice 2", "Practice 3"],
    "fuel_used": false,
    "app_version": "1.2.0",
    "created_at": "2026-04-03T10:15:00"
  }
}
```

---

## 3. Gráficos expuestos

### 3.1 Tiempos de Vuelta

**Archivo**: `app/_charts.py` → `create_lap_times_chart()`

**Tipo**: Línea + marcadores (Plotly Express)

**Ejes**:

- X: número de vuelta (`currentLap`)
- Y: tiempo de vuelta en segundos (`lap_time_s`), formateado como `m:ss.sss`
- Color: compuesto de neumático

**Marcadores especiales**:

| Marcador | Color | Significado |
| --- | --- | --- |
| ▼ rojo `#E8002D` | Pirelli rojo | Pit con cambio de neumáticos |
| ▼ gris `#888888` | Gris | Pit sin cambio de neumáticos (ajuste, penalización…) |

Las vueltas con `pit_stop=True` **no entran en la regresión** del modelo para no sesgar el intercept con tiempos inflados por el pit lane.

**Ejemplo**:

| Vuelta | Compuesto  | Tiempo   |
| ------ | ---------- | -------- |
| 1      | Medium     | 1:37.412 |
| 8      | Medium     | 1:38.540 |
| 15 ▼   | *Pit (cambio ruedas)* | — |
| 21     | Soft       | 1:36.801 |

**Lógica del eje Y**: Los ticks se calculan en pasos de 5 segundos entre `t_min` y `t_max`, redondeados al múltiplo de 5 inferior/superior.

```python
step = 5
tick_vals = range(int(t_min // step) * step, int(t_max) + step + 1, step)
```

---

### 3.2 Degradación de Neumáticos

**Archivo**: `app/_charts.py` → `create_degradation_chart()`

**Tipo**: Scatter (real) + Línea discontinua (modelo)

**Ejes**:

- X: edad del neumático en vueltas (`tire_age`)
- Y: tiempo de vuelta en segundos

**Qué muestra**: Para cada compuesto, superpone los puntos reales con la recta de regresión del modelo de degradación.

**Ejemplo** con `Medium (a=97.5, b=0.08)`:

| Edad (vueltas) | Tiempo predicho | Tiempo real |
| -------------- | --------------- | ----------- |
| 0              | 1:37.500        | 1:37.412    |
| 5              | 1:37.900        | 1:37.960    |
| 10             | 1:38.300        | 1:38.210    |
| 15             | 1:38.700        | 1:38.850    |

La pendiente `b = 0.08` s/vuelta indica que cada vuelta de desgaste cuesta ~80 ms.

---

### 3.3 Temperatura Pista vs Aire

**Archivo**: `app/_charts.py` → `create_temperatures_chart()`

**Tipo**: Líneas múltiples

**Series**:

- Pista (`trackTemp`)
- Aire (`airTemp`)
- Neumáticos: Delantero Izq/Der, Trasero Izq/Der (`flTemp`, `frTemp`, `rlTemp`, `rrTemp`)

**Eje X**: timestamp del CSV.

> **Nota**: Las temperaturas provienen del juego (F1 Manager 2024), no son valores reales de F1.

---

### 3.4 Evolución Edad Neumático / Compuesto

**Archivo**: `app/_charts.py` → `create_compound_evolution_chart()`

**Tipo**: Scatter con tamaño proporcional al tiempo de vuelta.

**Ejes**:

- X: número de vuelta
- Y: edad del neumático
- Color: compuesto
- Tamaño del punto: proporcional a `lap_time_s`

Este gráfico permite visualizar cuándo se hizo el pit stop (reseteo de edad a 0) y cómo evoluciona el desgaste a lo largo de la carrera/sesión.

---

### 3.5 Análisis de Residuos

**Archivo**: `app/_tab_analysis.py` → `render_metrics_tab()`

**Tipo**: Scatter

**Ejes**:

- X: edad del neumático
- Y: residuo en segundos = `lap_time_real − lap_time_predicho`

**Interpretación**:

- Residuos cerca de 0 → modelo bien ajustado.
- Patrón en forma de curva en los residuos → la degradación no es lineal para ese stint (señal de mejora posible con modelo cuadrático).

**Ejemplo**:

```text
Edad  Real     Predicho  Residuo
  0   97.41    97.50     -0.09
  5   97.96    97.90     +0.06
 10   98.21    98.30     -0.09
 15   98.85    98.70     +0.15   ← ligero aumento de residuo
```

---

### 3.6 Histograma de Tiempos de Vuelta

**Archivo**: `app/_tab_analysis.py` → `render_histogram_tab()`

**Tipo**: Histograma (20 bins por defecto, 15 por compuesto)

Muestra la distribución de frecuencias de `lap_time_s`. Una distribución estrecha y simétrica indica consistencia. Una cola larga a la derecha sugiere vueltas lentas por tráfico, safety car o pit entry.

Junto al histograma se muestra la tabla de estadísticas descriptivas estándar (count, mean, std, min, 25%, 50%, 75%, max).

---

### 3.7 Distribución por Compuesto (Boxplot)

**Archivo**: `app/_tab_analysis.py` → `render_compounds_tab()`

**Tipo**: Box plot (Plotly Express)

Muestra la distribución completa de tiempos por compuesto: mediana, cuartiles e IQR. Permite comparar visualmente cuál compuesto produce tiempos más bajos y más consistentes.

**Tabla complementaria** (`compound_stats`):

| Compuesto | Vueltas | Media (s) | Desv. Est. (s) | Mejor (s) | Peor (s) |
| --------- | ------- | --------- | -------------- | --------- | -------- |
| Soft      | 12      | 96.80     | 0.42           | 96.21     | 97.55    |
| Medium    | 24      | 97.85     | 0.31           | 97.40     | 98.62    |
| Hard      | 18      | 98.60     | 0.28           | 98.12     | 99.10    |

---

### 3.8 Consistencia — Coeficiente de Variación

**Archivo**: `app/_tab_analysis.py` → `render_consistency_tab()`

**Tipo**: Gráfico de barras con línea de referencia roja en CV = 2%

Muestra el CV (%) por compuesto. La línea roja discontinua a 2% marca el umbral de "buena consistencia". Ver [sección 6.1](#61-desviación-estándar-y-cv) para la fórmula.

---

## 4. Cálculos del modelo de degradación

**Archivo**: `f1m/modeling.py` → `fit_degradation_model()`

### 4.1 Modelo lineal simple (2 parámetros)

Se utiliza regresión lineal por mínimos cuadrados ordinarios (OLS) cuando **no hay datos de combustible** fiables.

$$\text{lap\_time} = a + b \cdot \text{tire\_age}$$

Donde:

- $a$ = tiempo base (intercept): tiempo de vuelta en la vuelta 0 de ese stint
- $b$ = degradación por vuelta (slope): segundos añadidos por cada vuelta adicional de desgaste

**Cálculo en código**:

```python
A = np.column_stack([np.ones_like(X_age), X_age])
coef, *_ = np.linalg.lstsq(A, y, rcond=None)
a, b_age = coef
```

**Ejemplo**:

- Datos Medium: 12 vueltas, `tire_age` de 0 a 11, tiempos entre 97.4 s y 98.4 s
- Resultado: `a = 97.50`, `b = 0.082`
- Interpretación: a vuelta 10, el modelo predice `97.50 + 0.082 × 10 = 98.32 s`

---

### 4.2 Modelo con corrección de combustible (3 parámetros)

Se activa automáticamente cuando la columna `fuel` tiene **≥ 5 valores** con desviación estándar > 0.5 kg.

$$\text{lap\_time} = a + b \cdot \text{tire\_age} + c \cdot \text{fuel}$$

Donde:

- $a$ = intercept base
- $b$ = degradación de neumático (s/vuelta)
- $c$ = efecto del combustible (s/kg) — típicamente negativo, ya que más combustible = coche más pesado = más lento

**Ejemplo**:

- `a = 95.20`, `b = 0.070`, `c = 0.045`
- Al inicio con 100 kg: `95.20 + 0.070 × 0 + 0.045 × 100 = 99.70 s`
- Al final con 10 kg (30 vueltas): `95.20 + 0.070 × 30 + 0.045 × 10 = 97.75 s`
- Delta total por combustible: ~2.0 s de ganancia al quemar 90 kg durante la carrera

---

### 4.3 Modelo con temperatura de pista (4 parámetros)

Se activa cuando `trackTemp.std() > 2.0 °C` en los datos de práctica.

$$\text{lap\_time} = a + b \cdot \text{tire\_age} + c \cdot \text{fuel} + d \cdot \text{trackTemp}$$

Donde:

- $d$ = efecto de temperatura (s/°C), típicamente positivo: pista más caliente = neumático más degradado = más lento
- La temperatura de referencia es `TEMP_REF_CELSIUS = 40.0 °C` absorbida en el intercept $a$

En el planificador se pasa `race_temp` y se calcula `a_eff = a + d × race_temp` antes de evaluar el stint.

**Ejemplo**: `d = 0.012` → cada grado extra de temperatura de pista añade ~12 ms por vuelta

---

### 4.4 Tiempo de stint

**Función**: `f1m/modeling.py` → `stint_time()`

Calcula el tiempo **total** de un stint de `laps` vueltas usando la suma de la progresión aritmética del modelo simple:

$$\text{stint\_time}(a, b, n) = n \cdot a + b \cdot \frac{(n-1) \cdot n}{2}$$

Esta es la suma exacta de $\sum_{k=0}^{n-1}(a + b \cdot k)$.

**Ejemplo** con `a = 97.50`, `b = 0.082`, `n = 15`:

$$15 \times 97.50 + 0.082 \times \frac{14 \times 15}{2} = 1462.5 + 8.61 = 1471.11 \text{ s} \approx 24\text{ min } 31\text{ s}$$

---

### 4.5 Filtros de datos previos al ajuste

Antes de ajustar el modelo se aplican tres filtros en cascada:

1. **Vueltas de boxes**: Se eliminan las vueltas con `pit_stop = True` (tiempos inflados por el pit lane, +20–30 s).
2. **Condiciones especiales**: Se eliminan las vueltas con `safety_car = True` o `rain = True`.
3. **Outlier z-score**: Se eliminan vueltas cuyo tiempo se desvía más de 3 desviaciones estándar de la media del compuesto.

```python
z = (lap_time_s - media) / std
filtrado = datos[abs(z) < 3]
```

**Requisito mínimo**: ≥ 5 vueltas y ≥ 2 valores únicos de `tire_age` por compuesto tras el filtrado.

---

## 5. Métricas de calidad del modelo

**Archivo**: `app/_metrics.py` → `calculate_model_metrics()`

### 5.1 MAE (Error Absoluto Medio)

$$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |y_i - \hat{y}_i|$$

Donde $y_i$ es el tiempo real y $\hat{y}_i$ es el tiempo predicho por el modelo.

**Interpretación práctica**:

- MAE < 0.3 s → modelo excelente
- MAE 0.3–0.8 s → aceptable
- MAE > 0.8 s → modelo poco fiable (datos insuficientes o degradación no lineal)

**Ejemplo**: Si el modelo predice tiempos con error medio de 0.24 s, en un stint de 20 vueltas el error acumulado estimado es ~4.8 s de cómputo.

---

### 5.2 R² (Coeficiente de Determinación)

$$R^2 = 1 - \frac{SS_{res}}{SS_{tot}} = 1 - \frac{\sum(y_i - \hat{y}_i)^2}{\sum(y_i - \bar{y})^2}$$

**Interpretación**:

- $R^2 = 1.0$ → ajuste perfecto
- $R^2 > 0.85$ → buena correlación lineal entre edad y tiempo
- $R^2 < 0.5$ → la degradación no sigue bien un patrón lineal

**Nota**: Si $SS_{tot} = 0$ (todos los tiempos son iguales), se devuelve $R^2 = 0$ para evitar división por cero.

---

## 6. Consistencia del piloto

**Archivo**: `app/_metrics.py` → `calculate_consistency_metrics()`

### 6.1 Desviación estándar y CV

Por cada compuesto (mínimo 3 vueltas):

$$\sigma = \sqrt{\frac{1}{n-1}\sum_{i=1}^{n}(y_i - \bar{y})^2}$$

$$\text{CV} (\%) = \frac{\sigma}{\bar{y}} \times 100$$

**Ejemplo**:

- Medium: media = 97.85 s, std = 0.31 s → CV = 0.317 %
- Soft: media = 96.80 s, std = 0.85 s → CV = 0.878 %
- El piloto es más consistente en Medium que en Soft.

**Umbral de referencia**: CV < 2% se considera consistencia adecuada (línea roja en el gráfico de barras).

---

## 7. Planificador de estrategia

**Archivo**: `f1m/planner.py` → `enumerate_plans()`

### 7.1 Enumeración de planes (DP + backtracking)

El planificador busca todas las combinaciones válidas de stints `(compuesto, vueltas)` que cubran exactamente `race_laps` vueltas, ordenando por tiempo total estimado.

**Algoritmo**: Programación dinámica con memoización (`_plan_cache`). Para cada estado `(vueltas_restantes, paradas_usadas, último_compuesto, nivel_combustible, compuestos_usados)`, calcula recursivamente los mejores sub-planes.

**Fórmula de tiempo total**:

$$T_{total} = \sum_{i=1}^{N_{stints}} T_{stint_i} + (N_{stints} - 1) \times \text{pit\_loss}$$

**Ejemplo** (Bahrain, 57 vueltas, pit_loss = 22 s):

| Plan | Stints              | Tiempo Total |
| ---- | ------------------- | ------------ |
| 1    | Medium×23 + Hard×34 | 5481.2 s     |
| 2    | Soft×15 + Medium×42 | 5493.8 s     |
| 3    | Medium×28 + Soft×29 | 5498.1 s     |

### 7.2 Coste de pit stop

Cada parada añade `pit_loss` segundos al tiempo total. El valor por defecto es **22 s** (configurable en la UI de 5 a 60 s).

```text
T_total = T_stints + número_paradas × pit_loss
```

### 7.3 Restricción de dos compuestos

Cuando está activa (`require_two_compounds = True`), se descartan los planes donde todos los stints usan el mismo compuesto (para carreras > 15 vueltas). Esto refleja el reglamento de F1 que obliga a usar al menos 2 compuestos secos distintos en carrera.

### 7.4 Viabilidad por combustible

Cuando `use_fuel = True` y el modelo tiene 3 coeficientes, en cada stint se verifica que el nivel de combustible no sea negativo en ninguna vuelta:

```python
fuel_series = fuel_cursor - cons_per_lap * arange(0, laps)
if any(fuel_series < 0):
    plan descartado → float('inf')
```

**Estimación automática del consumo**: El botón "Auto consumo" calcula la mediana de las diferencias consecutivas de `fuel` entre vueltas, filtrando valores no plausibles (fuera del rango 0–5 kg/vuelta).

```python
diffs = -fuel_series.diff().dropna()
plausible = diffs[(diffs > 0) & (diffs < 5)]
cons_estimado = plausible.median()
```

---

## 8. Recomendación en vivo

**Archivo**: `f1m/planner.py` → `live_pit_recommendation()`

Evalúa una **ventana de 12 vueltas** (configurable) para decidir cuándo hacer el pit stop y qué compuesto montar.

**Para cada vuelta candidata de pit** $p \in [1, \min(12, \text{vueltas\_restantes})]$:

1. Calcula el tiempo hasta parar: `time_current` (siguiendo en pista con el neumático actual)
2. Calcula el mejor tiempo restante con cada compuesto disponible tras el pit: `time_new`
3. Tiempo total = `time_current + pit_loss + time_new`

Se elige el escenario con menor tiempo total proyectado.

**Ejemplo** (vuelta 35 de 57, Medium con 12 vueltas de vida, pit_loss = 22 s):

| Parar en vuelta | Seguir | Tiempo hasta pit | Mejor compuesto tras pit | Tiempo restante | **Total**    |
| --------------- | ------ | ---------------- | ------------------------ | --------------- | ------------ |
| 36              | 1 v    | 98.2 s           | Hard                     | 1854.1 s        | **1974.3 s** |
| 38              | 3 v    | 295.8 s          | Hard                     | 1689.4 s        | 2007.2 s     |
| 42              | 7 v    | 699.1 s          | Soft                     | 1345.9 s        | 2067.0 s     |

→ Recomendación: **Parar en vuelta 36, montar Hard**.

---

## 9. Condiciones especiales

**Archivo**: `app/_tab_conditions.py`

### 9.1 Safety Car

Calcula el enlentecimiento medio comparando vueltas bajo safety car vs vueltas normales:

$$\text{Enlentecimiento SC (\%)} = \left(\frac{\bar{t}_{SC}}{\bar{t}_{normal}} - 1\right) \times 100$$

El multiplicador usado en los modelos es **1.5** (vuelta SC ≈ 50% más lenta que vuelta normal).

### 9.2 Lluvia

Misma lógica que safety car comparando vueltas con lluvia vs vueltas secas.

El multiplicador usado es **1.3** (vuelta húmeda ≈ 30% más lenta que seca).

### 9.3 Simulador de impacto

Permite ajustar sliders de porcentaje de vueltas SC y lluvia y calcular el impacto en el tiempo base de cada compuesto usando `adjust_lap_time_for_conditions()`:

```python
tiempo_ajustado = tiempo_base × multiplicador_SC × multiplicador_lluvia
```

**Ejemplo**: Compuesto Medium, `a = 97.5 s`

- Sin condiciones: 97.5 s
- Con Safety Car: 97.5 × 1.5 = **146.3 s**
- Con Lluvia: 97.5 × 1.3 = **126.75 s**
- SC + Lluvia: 97.5 × 1.5 × 1.3 = **190.1 s**

---

## 10. Detección de pit stops

**Archivo**: `f1m/telemetry.py` → `detect_pit_events()`

La función produce **dos columnas booleanas** independientes:

| Columna | Uso |
| --- | --- |
| `pit_stop` | Cualquier entrada a boxes (visualización en gráfico) |
| `tire_change_pit` | Solo cuando hubo cambio real de neumáticos (corte de stint, filtro de modelo) |

**Heurísticas para `tire_change_pit`** (cambio real de rueda):

| Heurística | Descripción |
| --- | --- |
| `reset_zero` | `tire_age == 0` tras haber sido `> 0` y `lap > 0` |
| `age_drop` | `tire_age < tire_age_anterior` con diferencia ≥ 2 vueltas |
| `comp_change` | Cambio de compuesto con `tire_age ≤ 1` |

**Heurística adicional para `pit_stop`** (entrada a boxes sin necesariamente cambiar ruedas):

| Heurística | Descripción |
| --- | --- |
| `pit_status_col` | `pitstopStatus` del CSV contiene alguno de: `Entering`, `Queuing`, `Stopped`, `Exiting`, `Jack Up`, `Releasing`, `Approach`, `Penalty` |

**Impacto en los stints**: `build_stints()` usa `tire_change_pit` (no `pit_stop`) para iniciar un stint nuevo, por lo que una parada sin cambio de ruedas no fragmenta incorrectamente el stint.

---

## 11. Margen de mejora por área

### 11.1 Modelo de degradación

| Mejora                              | Descripción                                                            | Impacto esperado                                                                                                                                               |
| ----------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Modelo cuadrático**               | $\text{time} = a + b \cdot \text{age} + d \cdot \text{age}^2$          | Captura el "acantilado" de degradación en neumáticos blandos que se acelera en las últimas vueltas. Reduciría el MAE ~20–30% en compounds con caída no lineal. |
| **Degradación logarítmica**         | $\text{time} = a + b \cdot \ln(1 + \text{age})$                        | Útil para compuestos que se degradan rápido al principio y luego se estabilizan.                                                                               |
| **Intervalo de confianza**          | Calcular y mostrar bandas ±1σ alrededor de la recta de regresión       | Ayuda a visualizar la incertidumbre del modelo; actualmente no se muestra.                                                                                     |
| **Pesos por vuelta**                | Dar más peso a las vueltas recientes en el ajuste OLS                  | Mejora la predicción para stints largos donde el comportamiento cambia.                                                                                        |
| **Eliminación de outliers por IQR** | Complementar el filtro z-score con IQR para distribuciones asimétricas | Más robusto que solo z-score cuando hay vueltas de in-lap/out-lap.                                                                                             |

### 11.2 Planificador de estrategia

| Mejora                               | Descripción                                                                           | Impacto esperado                                                                                 |
| ------------------------------------ | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Safety car probabilístico**        | Añadir `P(SC)` como parámetro y calcular el valor esperado del tiempo total           | Permite estrategias que aprovechan un SC probable (entrar a pistar bajo SC virtual).             |
| **Undercut / Overcut explícito**     | Modelar el beneficio de ganar posición en pista al ser el primero en parar vs esperar | Actualmente el planificador optimiza tiempo puro sin considerar cobertura de rivales.            |
| **Stint mínimo dinámico**            | Calcular el stint mínimo real de cada compuesto desde los datos (no slider fijo)      | Evita planes con stints irreales de 3–4 vueltas en compuestos duros.                             |
| **Top-K configurable**               | Exponer el parámetro `top_k` (actualmente fijo en 3) en la UI                         | Útil para comparar más opciones estratégicas.                                                    |
| **Restricción de stint máximo real** | Usar la duración máxima observada en práctica (actualmente: `max_tire_age + 2`)       | Añadir un margen configurable y/o basado en tiempo de vuelta umbral (ej. > +3% del tiempo base). |

### 11.3 Recomendación en vivo

| Mejora                                    | Descripción                                                                      | Impacto esperado                                                        |
| ----------------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **Ventana de lookahead adaptativa**       | Adaptar la ventana de 12 vueltas según las vueltas restantes                     | Evita recomendar un pit stop en vuelta 55 de 57, que no tiene sentido.  |
| **Considerar tiempo de vuelta del rival** | Integrar datos del oponente para calcular undercut                               | Funcionalidad nueva: requeriría datos de múltiples pilotos en paralelo. |
| **Historial de recomendaciones**          | Guardar en `st.session_state` el historial de recomendaciones para ver evolución | Ayuda a entender cómo cambia la recomendación vuelta a vuelta.          |

### 11.4 Métricas y visualizaciones

| Mejora                                          | Descripción                                                                        |
| ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| **Bandas de confianza en chart de degradación** | Añadir ±1σ como banda sombreada sobre la curva del modelo.                         |
| **Heatmap de tiempos por vuelta y compuesto**   | Visualización matricial para identificar patrones de degradación a golpe de vista. |
| **Evolución del R² con más datos**              | Mostrar cómo mejora el R² a medida que se acumulan más sesiones de práctica.       |
| **Comparación entre pilotos**                   | Superponer los modelos de Alonso y Stroll en el mismo gráfico de degradación.      |
| **Score compuesto de consistencia**             | Combinar CV, MAE y R² en un índice único de 0–100 para resumen ejecutivo.          |

### 11.5 Datos y pipeline

| Mejora                                          | Descripción                                                                                                                |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Normalización por temperatura de pista**      | Ajustar los tiempos de vuelta al comparar sesiones con temperaturas muy distintas (ej. P1 vs Q3).                          |
| **Corrección de combustible en in-lap/out-lap** | Descartar automáticamente la primera y última vuelta de cada stint del modelo, no solo por z-score.                        |
| **Integración multi-sesión automática**         | `collect_practice_data()` ya combina sesiones; exponer en la UI qué sesiones contribuyeron y con cuántas vueltas cada una. |

---

*Actualizado el 4 de abril de 2026 desde el codebase de `c:\f1_pitstop`.*
