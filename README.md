# F1 Pitstop Strategy Dashboard

![CI](https://github.com/doski2/f1_pitstop/actions/workflows/ci.yml/badge.svg)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Analítica avanzada y planificación de estrategia de paradas para datos exportados de **F1 Manager 2024**.

## ✨ Características

- 🔍 **Detección automática de stints y paradas** basada en heurísticas
- 📊 **Modelado de degradación** lineal por compuesto (con soporte opcional para combustible)
- 🏁 **Enumeración de planes de estrategia** con restricciones FIA simplificadas
- 📈 **Visualizaciones interactivas** de tiempos, temperaturas y desgaste
- 🎯 **Recomendación en vivo** de próxima parada usando heurísticas inteligentes
- 💾 **Modelos precomputados** guardados en formato JSON
- 🔧 **Scripts auxiliares** para curación de datos y inicialización de modelos
- 📏 **Métricas de calidad del modelo** (MAE, R², análisis de residuos)
- 📊 **Análisis estadístico avanzado** (histogramas, consistencia, comparación de compuestos)
- ⚡ **Optimizaciones de rendimiento** con reducción de memoria del 27.1%
- 🧪 **Herramientas de benchmarking** automatizadas para validación de rendimiento
- 🚀 **Sistema optimizado** con memoización y carga eficiente de datos

> **Descargo de responsabilidad**: Este proyecto no está afiliado a Frontier Developments ni a la FIA. Los cálculos son simplificaciones analíticas y no representan estrategias oficiales de F1.

---

## 📋 Tabla de Contenidos

- [Requisitos](#requisitos)
- [Instalacion](#instalacion)
- [Estructura de Datos](#estructura-de-datos)
- [Uso del Dashboard](#uso-del-dashboard)
- [Scripts Auxiliares](#scripts-auxiliares)
- [Herramientas de Rendimiento](#herramientas-de-rendimiento)
- [Ejemplos de Uso](#ejemplos-de-uso)
- [Configuracion](#configuracion)
- [Limitaciones](#limitaciones)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

---

## Requisitos

- **Python**: 3.10 o superior
- **Dependencias**: Ver `requirements.txt`

---

## Instalacion

1. **Clona el repositorio**:

   ```bash
   git clone https://github.com/doski2/f1_pitstop.git
   cd f1_pitstop
   ```

2. **Crea un entorno virtual**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # En Windows: .\.venv\Scripts\Activate.ps1
   ```

3. **Instala las dependencias**:

   ```bash
   pip install -U pip
   pip install -r requirements.txt
   ```

4. **Ejecuta el dashboard**:

   ```bash
   streamlit run app/dashboard.py
   ```

---

## Estructura de Datos

El proyecto espera datos exportados de F1 Manager 2024 en la siguiente estructura:

```text
logs_in/
└── exported_data/
    └── <Track>/
        └── <Session>/  # Practice 1, Practice 2, Qualifying, Race, etc.
            └── <Driver>/
                └── archivo.csv
```

**Ejemplo real**:

```text
logs_in/exported_data/Bahrain/Practice 1/Fernando Alonso/2025-08-24_01-15-07_AstonMartin2_Telemetry_Bahrain_Practice 1.csv
```

Los datos curados se almacenan en `curated/` en formato Parquet para un acceso más eficiente.

---

## Uso del Dashboard

### Inicio Rápido

1. **Selecciona parámetros**: Circuito, Sesión, Piloto y archivo de telemetría
2. **Revisa análisis**: Lap Summary, Stints detectados y cumplimiento FIA
3. **Configura estrategia**: Carga o genera modelo, ajusta pérdida de pit y consumo
4. **Calcula planes**: Genera estrategias óptimas y guarda el modelo
5. **Analiza métricas**: Revisa métricas del modelo, histogramas y comparaciones

### Pestañas de Análisis

- **Lap Times**: Evolución de tiempos de vuelta
- **Tº Neumáticos**: Temperaturas de neumáticos por rueda
- **Tº Pista/Aire**: Condiciones ambientales
- **Evolución Compuesto**: Degradación por tipo de neumático
- **Estrategia**: Planes de parada generados
- **Desgaste**: Porcentaje de desgaste por rueda
- **Métricas Modelo**: Calidad del modelo (MAE, R², residuos)
- **Histograma**: Distribución estadística de tiempos
- **Consistencia**: Análisis de variabilidad del piloto
- **Comparación Compuestos**: Análisis comparativo entre neumáticos

### Modelos Precomputados

Los modelos se almacenan en JSON con este formato:

```json
{
  "metadata": {
    "track": "Bahrain",
    "driver": "Fernando Alonso",
    "sessions_included": ["Practice 1", "Practice 2"],
    "fuel_used": true,
    "saved_at": "2025-11-13T10:00:00"
  },
  "models": {
    "SOFT": [94.3, 0.145],
    "MEDIUM": [95.1, 0.120, 0.010]
  }
}
```

Ubicación: `models/<Track>/<Driver>_model.json`

---

## Scripts Auxiliares

### Curación de Datos (`app/curate.py`)

Procesa CSVs crudos y genera datasets por vuelta con features adicionales:

```bash
python app/curate.py
```

Características:

- Cálculo de pace_index
- Medianas móviles
- Pendiente de combustible
- Guardado en Parquet

### Inicialización de Modelos (`app/init_models.py`)

Genera modelos base usando datos de práctica:

```bash
python -m app.init_models --track Bahrain --driver "Fernando Alonso"
```

**Parámetros**:

- `--track`: Nombre del circuito
- `--driver`: Nombre del piloto
- `--force`: Sobrescribir modelos existentes

### Scripts de Utilidad

- `scripts/fix_streamlit_width.py`: Migra parámetros de ancho de Streamlit
- `scripts/run_dashboard.ps1`: Ejecuta el dashboard en Windows PowerShell

---

## Herramientas de Rendimiento

El proyecto incluye herramientas automatizadas para medir y validar el rendimiento de las optimizaciones implementadas.

### Benchmark del Sistema Principal

Ejecuta pruebas de rendimiento del núcleo del sistema:

```bash
python benchmark_performance.py
```

**Métricas medidas:**

- ⏱️ Tiempo de carga de datos de práctica
- 🧠 Optimización de memoria (27.1% de ahorro validado)
- 📊 Ajuste de modelos de degradación
- 🏁 Enumeración de planes de carrera con memoización

### Benchmark del Dashboard

Simula el rendimiento del dashboard de Streamlit:

```bash
python benchmark_dashboard.py
```

**Métricas medidas:**

- 📥 Carga de datos multi-piloto con optimización automática
- 🤖 Flujo completo de ajuste de modelos desde datos de práctica
- 🎯 Cálculo de estrategias de carrera optimizadas

### Documentación de Rendimiento

Para información detallada sobre las métricas de rendimiento y resultados de benchmarking, consulta [`PERFORMANCE_README.md`](PERFORMANCE_README.md).

---

## Ejemplos de Uso

### Ejemplo 1: Análisis Básico de Telemetría

```python
from f1m.telemetry import load_session_csv, build_lap_summary, build_stints

# Cargar datos
df = load_session_csv("path/to/telemetry.csv")

# Construir resumen de vueltas
laps = build_lap_summary(df)

# Detectar stints
stints = build_stints(laps)

print(f"Vueltas analizadas: {len(laps)}")
print(f"Stints detectados: {len(stints)}")
```

### Ejemplo 2: Modelado de Degradación

```python
from f1m.modeling import collect_practice_data, fit_degradation_model

# Recopilar datos de práctica
practice_data = collect_practice_data(Path("curated"), "Bahrain", "Fernando Alonso")

# Ajustar modelos
models = fit_degradation_model(practice_data)

for compound, params in models.items():
    print(f"{compound}: intercept={params[0]:.2f}, slope={params[1]:.4f}")
```

### Ejemplo 3: Generación de Planes de Estrategia

```python
from f1m.planner import enumerate_plans

# Parámetros de carrera
race_laps = 57  # Bahrain Grand Prix
compounds = ["SOFT", "MEDIUM", "HARD"]
models = {"SOFT": (94.3, 0.145), "MEDIUM": (95.1, 0.120)}
pit_loss = 20.0  # segundos

# Generar planes
plans = enumerate_plans(race_laps, compounds, models, practice_data, pit_loss)

for plan in plans[:3]:  # Top 3 planes
    print(f"Tiempo total: {plan['total_time']:.2f}s")
    print(f"Stints: {plan['stints']}")
```

### Ejemplo de Uso de la API

```bash
python examples/api_usage_example.py
```

Este script demuestra todas las funcionalidades principales:

- Carga y análisis de telemetría
- Modelado de degradación de neumáticos
- Planificación de estrategias de parada

---

## Configuracion

### Añadir Nuevo Circuito

Edita `TRACK_LAPS` en `app/dashboard.py`:

```python
TRACK_LAPS = {
    "Bahrain": 57,
    "Jeddah": 50,
    "Melbourne": 58,
    # Añade tu circuito aquí
    "NuevoCircuito": 60
}
```

### Configuración de Streamlit

Crea `.streamlit/config.toml`:

```toml
[server]
headless = true
port = 8501

[browser]
gatherUsageStats = false
```

---

## Limitaciones

- Modelo de degradación lineal (no maneja curvas complejas ni Safety Cars)
- Reglas FIA simplificadas (sin todas las restricciones oficiales)
- No soporta comparación multi-piloto en tiempo real
- Requiere datos de telemetría exportados manualmente de F1 Manager

---

## Contribuir

¡Las contribuciones son bienvenidas! Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

### Guías de Desarrollo

- Usa `ruff` para linting y formato
- Ejecuta tests con `pytest`
- Actualiza documentación para cambios significativos

---

## Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

---

## 🙏 Agradecimientos

- Comunidad de F1 Manager por compartir conocimientos sobre telemetría
- Desarrolladores de Pandas, Plotly y Streamlit por herramientas excelentes
- Frontier Developments por crear F1 Manager 2024

---

**Versión**: 1.2.0 | **Última actualización**: Noviembre 2025
