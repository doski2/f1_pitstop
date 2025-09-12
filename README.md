# F1M Manager — Estrategia de Paradas (v1.1.0)

![CI](https://github.com/doski2/f1_pitstop/actions/workflows/ci.yml/badge.svg)

Analítica y planificación de estrategia de paradas para **F1 Manager 2024** con:
- Dashboard en Streamlit
- Modelado de degradación lineal por compuesto (opcionalmente con fuel)
- Enumeración de planes y recomendación de pit en vivo

## 🚀 Quickstart

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

## 📁 Estructura

```
f1m/
	telemetry.py   # telemetría: CSV, pitstops, lap summary, stints, FIA
	modeling.py    # degradación (a + b*edad [+ c*fuel]), utils
	planner.py     # enumerate_plans, live_pit_recommendation
dashboard.py      # UI Streamlit
init_models.py    # CLI para generar modelos por pista/piloto
strategy*.py      # shims de compatibilidad (no borrar si tienes scripts viejos)
```

## 📊 Datos de entrada

Organiza los CSV así:
```
logs_in/exported_data/<Track>/<Session>/<Driver>/*.csv
```
Ejemplo:
```
logs_in/exported_data/Bahrain/Practice/Leclerc/*.csv
logs_in/exported_data/Bahrain/Race/Leclerc/*.csv
```

**Campos esperados (principales):**
- `timestamp` (ISO/epoch ms), `currentLap`, `lastLapTime` (puede ser "m:ss.xxx" o float s)
- `compound`, `tire_age`
- Temperaturas: `trackTemp`, `airTemp`, `flTemp`, `frTemp`, `rlTemp`, `rrTemp`
- `fuel` (opcional)

> Si `lastLapTime` llega en formato `m:ss.xxx`, el parser lo convierte a segundos automáticamente.

## 🧠 Modelos

**Sin fuel**: `lap ≈ a + b_age * edad`  
**Con fuel**: `lap ≈ a + b_age * edad + c_fuel * fuel`

Entrena modelos desde prácticas con:
```bash
python init_models.py --data-root logs_in/exported_data --track Bahrain --driver Leclerc
```
Guarda en `models/<Track>/<Driver>_model.json`.

## 🗺️ Planes & Recomendación

- `enumerate_plans`: backtracking con límites (`max_stops`, `min_stint`) y chequeos básicos.
- `live_pit_recommendation`: ventana local (p.ej. próximas 12 vueltas) que selecciona la vuelta
	de parada y el compuesto del tramo final con menor tiempo proyectado (incluye pérdida de pit).

## ⚠️ Notas y limitaciones
- Modelos lineales: válidos como primera aproximación; no contemplan SC, VSC ni lluvia.
- Chequeo FIA simplificado.
- Fuel opcional: si no hay `fuel` fiable, el sistema funciona en modo solo “edad”.

## 🧪 Desarrollo

```bash
make install
make qa   # ruff + black + mypy + pytest (placeholder)
```

## 🤝 Contribuir
Ver `CONTRIBUTING.md`. Código de conducta en `CODE_OF_CONDUCT.md`.

## 📄 Licencia
MIT (ver `LICENSE`).
