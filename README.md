# Dashboard Estrategia de Paradas – F1 Manager 2024 (v1.0.2)

![CI](https://github.com/doski2/f1_pitstop/actions/workflows/ci.yml/badge.svg)

Analítica y planificación de estrategia de paradas para datos exportados de **F1 Manager 2024**.

- Detección de stints y paradas.
- Modelo lineal de degradación por compuesto (JSON persistente).
- Enumeración de estrategias (reglas FIA simplificadas).
- Visualizaciones (laps, temps, desgaste, track/air).
- Recomendación en vivo de pit.
- Capa adapter preparada para multi‑juego.

> Descargo: No afiliado a Frontier / FIA. Reglas simplificadas.

---
## 1. Requisitos

- Python 3.10+ (probado 3.10–3.13)
- Dependencias en `requirements.txt`

Instalación rápida (PowerShell):

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

## 2. Estructura de Datos de Entrada

```text
logs_in/
	exported_data/
		<Track>/
			<Session>/ (Practice 1 | Practice 2 | Practice 3 | Qualifying 1.. | Race)
				<Driver>/
					<archivo>.csv
```

Ejemplo ruta: `logs_in/exported_data/Bahrain/Practice 1/Fernando Alonso/2025-08-24_...csv`

## 4. Scripts

### 4.1 Curación (`app/curate.py`)

```bash
python app/curate.py --track Bahrain --input logs_in/exported_data/Bahrain --out curated/Bahrain
```

### 4.2 Modelos Iniciales (`app/init_models.py`)

```bash
python app/init_models.py --track Bahrain
```

## 5. Modelo de Degradación

Ecuación:

```text
lap_time = a + b_age * tire_age [+ c_fuel * fuel]
```

Ejemplo JSON:

```json
{"metadata":{"track":"Bahrain","driver":"Fernando Alonso","sessions_included":["Practice 1"],"fuel_used":true,"saved_at":"2025-08-25T14:33:10"},"models":{"Soft":[94.3,0.145],"Medium":[95.1,0.120,0.010]}}
```

## 6. Uso en el Dashboard

1. Selecciona Circuito / Sesión / Piloto / Archivo CSV.
2. Revisa lap summary y stints.
3. (Estrategia) Carga modelo precomputado o genera uno nuevo.
4. Ajusta parámetros: pérdida de pit, consumo, vueltas totales.
5. Calcula estrategias y revisa stints previstos.
6. Guarda modelo para reutilizar.

## 7. Añadir un Nuevo Circuito

Editar `TRACK_LAPS` en `app/dashboard.py`.

## 8. Buenas Prácticas

- No subir datos crudos masivos.
- Añadir dataset ejemplo opcional.
- Verificar `pyarrow` instalado para Parquet.

## 9. Limitaciones

- Modelo lineal simple.
- Sin Safety Car / tráfico.
- Sin multi‑piloto simultáneo.
- Reglas FIA simplificadas.

## 10. Roadmap

- Métricas MAE/R².
- Historial modelos.
- Modelos no lineales.
- Monte Carlo (Safety Car).
- Selector multi‑juego.

## 11. Contribuir

1. Fork / rama feature.
2. Commits claros (ES o EN).
3. PR con descripción y pruebas manuales.

## 12. Licencia

MIT – ver `LICENSE`.

## 13. Descargo

Software "tal cual" sin garantías. No distribuye datos originales del juego.

---
¡Felices estrategias! 🏁
