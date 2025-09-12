# F1M Manager — Estrategia de Paradas (v1.1.0)

![CI](https://github.com/doski2/f1_pitstop/actions/workflows/ci.yml/badge.svg)

Analítica y planificación de estrategia de paradas para **F1 Manager 2024** con:
# Dashboard Estrategia de Paradas – F1 Manager 2024 (v1.0.2)

![CI](https://github.com/doski2/f1_pitstop/actions/workflows/ci.yml/badge.svg)

Analítica y planificación de estrategia de paradas para datos exportados de **F1 Manager 2024**.

**Incluye**
- Detección de stints y paradas.
- Modelado lineal de degradación por compuesto (opcionalmente con combustible).
- Enumeración de planes de estrategia con restricciones FIA simplificadas.
- Gráficos de tiempos, temperaturas y desgaste (si existe).
- Recomendación en vivo de próxima parada (heurística).

> Descargo: No está afiliado a Frontier/FIA. Cálculos simplificados con fines analíticos.

---
## 1) Requisitos
- Python 3.10+
- `pip install -r requirements.txt`

## 2) Estructura de datos esperada
```text
logs_in/
	exported_data/
		<Track>/
			<Session>/  (Practice 1 | Practice 2 | Practice 3 | Qualifying 1.. | Race)
				<Driver>/
					archivo.csv
```
Ejemplo: `logs_in/exported_data/Bahrain/Practice 1/Fernando Alonso/2025-08-24_...csv`

## 3) Puesta en marcha
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
streamlit run dashboard.py
```

## 4) Modelos precomputados
Formato JSON:
```json
{
	"metadata": {
		"track": "Bahrain",
		"driver": "Fernando Alonso",
		"sessions_included": ["Practice 1", "Practice 2"],
		"fuel_used": true,
		"saved_at": "2025-08-25T14:33:10"
	},
	"models": {
		"Soft":   [94.3, 0.145],
		"Medium": [95.1, 0.120, 0.010]
	}
}
```
Los modelos se cargan/guardan automáticamente desde `models/<Track>/<Driver>_model.json`.

## 5) Uso del Dashboard
1. Selecciona Circuito / Sesión / Piloto / Archivo.
2. Revisa *Lap Summary*, *Stints* y reglas simplificadas FIA.
3. En **Estrategia**: genera/carga modelo, ajusta pérdida de pit, consumo y vueltas.
4. Calcula planes y guarda el modelo.

## 6) Scripts auxiliares
### `curate.py`
Curación de CSV → dataset por vuelta + features (pace_index, rolling medians, fuel slope) y guardado en Parquet.

### `init_models.py`
Genera modelos base por pista/piloto usando prácticas o fallback de primeras vueltas de carrera.

## 7) Añadir circuito
Edita `TRACK_LAPS` en `dashboard.py` y añade `'NuevoCircuito': <vueltas>`.

## 8) Limitaciones
- Modelo lineal (no curvas complejas ni SC).
- Reglas FIA simplificadas.
- No hay comparación multi-piloto simultánea.

## 9) Roadmap corto
- Métricas de calidad (MAE/R²) en UI.
- Versionado de modelos.
- Modelos no lineales / pieza a pieza.
- Simulación (SC/tráfico).

## 10) Licencia
MIT – ver `LICENSE`.

---
¡Felices estrategias! 🏁
