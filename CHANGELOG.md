# Changelog

## v1.2.0

### Nuevas Características

- **Métricas de Calidad del Modelo**: Nueva pestaña "Métricas Modelo" con análisis de MAE, R² y residuos para evaluar la calidad de los modelos de degradación
- **Análisis Estadístico Avanzado**:
  - Pestaña "Histograma" para distribución estadística de tiempos de vuelta
  - Pestaña "Consistencia" para análisis de variabilidad del piloto
  - Pestaña "Comparación Compuestos" para análisis comparativo entre tipos de neumáticos
- **Funciones de Cálculo**: Nuevas funciones `calculate_model_metrics()` y `calculate_consistency_metrics()` para análisis estadístico
- **Mejoras en Robustez**: Verificaciones defensivas para evitar errores cuando faltan DataFrames o columnas

### Mejoras

- Dashboard ampliado a 10 pestañas de análisis para mayor profundidad analítica
- Mejor manejo de errores en operaciones con DataFrames
- Compatibilidad mejorada con diferentes formatos de datos de telemetría
- **Optimización crítica de carga de datos**: `collect_practice_data()` ahora lee directamente desde archivos Parquet curados en lugar de procesar CSVs repetidamente
  - Eliminado procesamiento innecesario de datos ya procesados
- **Suite de Pruebas Completa**: Añadida cobertura de pruebas unitarias completa para todos los módulos principales
  - `test_telemetry.py`: 8 pruebas para optimización de memoria, carga de CSV, construcción de resúmenes de vuelta y validación de constantes
  - `test_common.py`: 3 pruebas para colección de datos de práctica con manejo de archivos Parquet
  - `test_planner.py`: 3 pruebas para enumeración de planes de carrera con memoización y restricciones de combustible
  - `test_modeling.py`: 4 pruebas para ajuste de modelos de degradación, cálculo de tiempos de stint y determinación de longitudes máximas de stint
  - Configuración de linting actualizada para permitir importaciones estándar en archivos de prueba
- **Herramientas de Benchmarking de Rendimiento**: Scripts automatizados para medir y validar el rendimiento de las optimizaciones
  - `benchmark_performance.py`: Pruebas de rendimiento del núcleo del sistema (carga de datos, optimización de memoria, ajuste de modelos, enumeración de planes)
  - `benchmark_dashboard.py`: Simulación del rendimiento del dashboard (carga de datos multi-piloto, flujos de modelado, cálculo de estrategias)
  - Métricas detalladas de tiempo de ejecución y uso de memoria para todas las operaciones críticas
- **Optimización de memoria en DataFrames**: Implementada función `optimize_dataframe_memory()` que reduce significativamente el uso de memoria
  - Conversión automática de `int64` a tipos más eficientes (`int32`, `int16`, `int8`) según el rango de valores
  - Conversión de `float64` a `float32` para todas las columnas numéricas de punto flotante
  - Aplicado automáticamente en `load_session_csv()`, `build_lap_summary()` y `collect_practice_data()`
  - Reducción típica del 50-70% en uso de memoria para datasets de telemetría
- **Eliminación de imports redundantes**: Reorganización completa del sistema de imports para reducir duplicación
  - Creado módulo `f1m.imports` con imports comunes centralizados
  - Actualizado `__init__.py` del paquete f1m para exponer imports estándar
  - Refactorizados todos los archivos del paquete f1m para usar imports consistentes
  - Corregidos imports incorrectos en archivos de ejemplo y scripts
  - Mejora en mantenibilidad y reducción de código duplicado
- **Optimizaciones de caché en Dashboard**: Implementación exhaustiva de caché para eliminar recálculos costosos en cada rerun de Streamlit
  - `@st.cache_data` agregado a funciones de carga de datos: `load_practice_data()`, `fit_degradation_models()`, `generate_race_plans()`
  - `@st.cache_data` agregado a funciones de cálculo: `calculate_model_metrics()`, `calculate_consistency_metrics()`, `load_precomputed_model()`
  - `@st.cache_data` agregado a funciones de visualización: `create_lap_times_chart()`, `create_degradation_chart()`, `create_temperatures_chart()`, `create_compound_evolution_chart()`
  - Funciones existentes (`load_and_process()`, `list_tracks()`, `list_sessions()`, `list_drivers()`) ya tenían caché optimizada
  - Reducción significativa de tiempo de carga y mejora en la experiencia de usuario
  - Caché inteligente que se invalida automáticamente cuando cambian los datos subyacentes
  - Mejora significativa en velocidad de carga (lectura directa vs parsing CSV + build_lap_summary)
  - Mantiene compatibilidad con fallback a procesamiento CSV si datos curados no existen
- **Optimización crítica del algoritmo de planificación**: `enumerate_plans()` reescrito con programación dinámica y memoización
  - Eliminada complejidad exponencial O(c^k * l) donde c=compuestos, k=paradas, l=longitud máxima stint
  - Implementada memoización con `@lru_cache` para evitar recalculos de subproblemas
  - Mejora drástica en rendimiento para carreras con muchos compuestos o stints largos
  - Mantiene compatibilidad completa con la API existente
- **Mejora en manejo de excepciones**: Reemplazadas todas las cláusulas genéricas `except Exception:` con excepciones específicas para mejor depuración
  - `f1m/common.py`: `collect_practice_data()` ahora captura `(FileNotFoundError, PermissionError, pd.errors.EmptyDataError, ValueError, KeyError)` para archivos Parquet y `(FileNotFoundError, PermissionError, pd.errors.EmptyDataError, pd.errors.ParserError, KeyError, ValueError)` para CSVs
  - `f1m/planner.py`: Conversión a float captura `(ValueError, TypeError)`
  - `app/strategy_model.py`: Conversión a float captura `(ValueError, TypeError)`
  - `app/strategy.py`: Carga de CSVs captura `(FileNotFoundError, PermissionError, pd.errors.EmptyDataError, pd.errors.ParserError, KeyError, ValueError)`
  - `app/init_models.py`: Procesamiento de CSVs captura `(FileNotFoundError, PermissionError, pd.errors.EmptyDataError, pd.errors.ParserError, KeyError, ValueError)`
  - `adapters/f1manager2024.py`: Conversión de timestamp captura `(ValueError, TypeError)`
  - `app/dashboard.py`: Carga de modelos JSON captura `(json.JSONDecodeError, FileNotFoundError, KeyError, ValueError)`
  - `app/curate.py`: Lectura de CSVs captura `(FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError)`
  - Mejora significativa en capacidad de depuración al identificar tipos específicos de errores en lugar de capturar todo genéricamente
- **Eliminación de constantes hardcodeadas**: Movidas rutas y nombres de columnas a constantes centralizadas para mejorar mantenibilidad
  - `f1m/telemetry.py`: Agregadas constantes `COL_LAP`, `COL_LAP_TIME`, `COL_COMPOUND`, `COL_TIRE_AGE`, `COL_TIMESTAMP`, `COL_SESSION`, `COL_FUEL`, `COL_SOURCE_FILE` para nombres de columnas
  - `f1m/telemetry.py`: Agregadas constantes `DIR_CURATED`, `DIR_MODELS`, `DIR_LOGS_IN`, `DIR_EXPORTED_DATA` para rutas de directorios
  - `f1m/telemetry.py`: Agregadas constantes `EXT_PARQUET`, `EXT_JSON`, `EXT_CSV` para extensiones de archivos
  - `f1m/common.py`: Reemplazado `"curated"` con `DIR_CURATED`
  - `f1m/common.py`: Reemplazado `"lap_time_s"` con `COL_LAP_TIME`
  - `app/strategy.py`: Agregadas constantes locales `COL_LAP`, `COL_LAP_TIME`, `COL_COMPOUND`, `COL_TIRE_AGE`, `COL_TIMESTAMP`, `COL_SESSION`, `COL_FUEL`, `COL_SOURCE_FILE`
  - `app/strategy.py`: Reemplazados todos los usos hardcodeados de `"currentLap"` con `COL_LAP`
  - `app/dashboard.py`: Importadas constantes de `f1m.telemetry` y reemplazados usos hardcodeados de nombres de columnas y rutas
  - `app/dashboard.py`: Reemplazado `"models"` con `DIR_MODELS`
  - `app/curate.py`: Importada constante `DIR_CURATED` y reemplazado `"curated"` con `DIR_CURATED`
  - `app/init_models.py`: Agregada constante `DEFAULT_DATA_ROOT` usando `DIR_LOGS_IN` y `DIR_EXPORTED_DATA`
  - Mejora significativa en mantenibilidad al centralizar configuración de rutas y nombres de columnas
  - Ruff: sin versión → 0.14.5
  - Pip actualizado a 25.3
- **Refactorización crítica**: Eliminada duplicación de código entre `f1m/modeling.py` y `app/strategy_model.py`
  - Movidas `collect_practice_data()` y `PRACTICE_SESSION_NAMES` a módulo común `f1m/common.py`
  - Actualizadas todas las importaciones para usar el módulo común
  - Mejor mantenibilidad y reducción de riesgo de inconsistencias

### Correcciones

- Resueltos errores de sintaxis en implementaciones de nuevas pestañas
- Corregidos KeyError en acceso a columnas de DataFrames
- Mejorada compatibilidad con versiones recientes de Streamlit
- Corregidos avisos de tipo y lint en `app/dashboard.py` (anotaciones `Optional`, aserciones y orden de imports con `ruff`)

## v1.1.0

## 2025-09-13

Cambios:

- Se añadió un shim en la raíz `init_models.py` que delega a `app.init_models` (compatibilidad de punto de entrada).
- Se actualizaron las exclusiones en `.gitignore` para ignorar cachés de análisis/testrunner (`.mypy_cache/`, `.pytest_cache/`).
- Cachés ligeras para listados (tracks/sesiones/pilotos/CSV).
- README reescrito y ordenado.
- CI sanitizado.
