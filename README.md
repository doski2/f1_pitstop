# Dashboard Estrategia de Paradas – F1 Manager 2024 (v1.0.0)

Analítica y planificación de estrategia de paradas para datos exportados de **F1 Manager 2024**. Incluye:

- Detección de stints y paradas de boxes.
- Modelado básico de degradación (por compuesto) y soporte para modelos precomputados.
- Evaluación de estrategias (enumeración de planes con restricciones FIA simplificadas).
- Visualización de tiempos de vuelta, temperaturas de neumáticos, pista/aire y desgaste (si está disponible).
- Recomendación en vivo de próxima parada (heurística sobre modelo lineal).

> Descargo: No está afiliado a Frontier / FIA. Las reglas y cálculos están simplificados y sirven solo con fines analíticos y educativos.

---
## 1. Requisitos

- Python 3.10+ (probado con 3.10–3.13)
- Dependencias en `requirements.txt`

Instalación rápida (Windows PowerShell):

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

	"metadata": {
		"track": "Bahrain",
		"driver": "Fernando Alonso",
		"sessions_included": ["Practice 1", "Practice 2"],
		"fuel_used": true,
		"saved_at": "2025-08-25T14:33:10"
	},
	"models": { "Soft": [94.3, 0.145], "Medium": [95.1, 0.120, 0.010] }

```text
logs_in/
	exported_data/
		<Track>/
			<Session>/  (Practice 1 | Practice 2 | Practice 3 | Qualifying 1.. | Race)
				<Driver>/
					archivo.csv
```
Ejemplo: `logs_in/exported_data/Bahrain/Practice 1/Fernando Alonso/2025-08-24_...csv`

## 4. Scripts Auxiliares
### 4.1 Curación de Datos (`curate.py`)
Convierte CSV crudos en dataset lap-level estandarizado + features derivadas (pace_index, rolling medians, fuel slope) y guarda en Parquet.

Ejemplo de uso:

```bash
python curate.py --track Bahrain --input logs_in/exported_data/Bahrain --out curated/Bahrain
```
Salida: `curated/<Track>/<Session>/<Driver>/*.parquet` y `summary_<Track>.csv`.

### 4.2 Modelos Iniciales (`init_models.py`)
Genera modelos de degradación por compuesto (lineal: tiempo = a + b_age*edad [+ c_fuel*fuel]). Usa prácticas; si faltan, toma muestras iniciales de carrera.
```bash
python init_models.py --track Bahrain
```
Salida: `models/<Track>/<Driver>_model.json`.

## 5. Modelo de Degradación
Actualmente lineal por compuesto. Formatos posibles de coeficientes:
 
```text
"Soft": [a, b_age]
{
	"metadata": {
		"track": "Bahrain",
		"driver": "Fernando Alonso",
		"sessions_included": ["Practice 1", "Practice 2"],
		"fuel_used": true,
		"saved_at": "2025-08-25T14:33:10"
	},
	"models": { "Soft": [94.3, 0.145], "Medium": [95.1, 0.120, 0.010] }
}
		"saved_at": "2025-08-25T14:33:10"
	},
## 6. Uso en el Dashboard

1. Selecciona Circuito / Sesión / Piloto / Archivo CSV.
2. Revisa lap summary y stints.
3. En pestaña Estrategia: opcionalmente carga modelo precomputado (checkbox) o genera uno nuevo.
4. Ajusta parámetros: pérdida de pit, consumo, vueltas totales.
5. Calcula estrategias y revisa stints previstos.
6. Guarda modelo (persistencia para próximas sesiones).
3. En pestaña Estrategia: opcionalmente carga modelo precomputado (checkbox) o genera uno nuevo.
## 7. Añadir un Nuevo Circuito
5. Calcula estrategias y revisa stints previstos.
Editar el diccionario `TRACK_LAPS` en `dashboard.py` añadiendo `'NuevoCircuito': <vueltas>`.

## 8. Buenas Prácticas / Publicación

- Limpiar datos confidenciales antes de subir.
- Añadir datasets de ejemplo (pequeños, anonimizados) o proveer script de descarga.
- Ejecutar `curate.py` y subir solo Parquets de ejemplo opcionales (no obligatorios).
- Verificar que `pyarrow` esté instalado para escritura Parquet.
- Añadir datasets de ejemplo (pequeños, anonimizados) o proveer script de descarga.
## 9. Limitaciones Actuales

- Modelo lineal (no contempla curvatura de degradación ni efectos de temperatura).
- Estrategias enumeradas sin simulación de Safety Car ni tráfico.
- No hay comparación multi-piloto simultánea.
- Validaciones FIA simplificadas (no contempla condiciones de neumáticos de lluvia detalladas).
- Estrategias enumeradas sin simulación de Safety Car ni tráfico.
## 10. Roadmap Corto

- Métricas de calidad de modelo (MAE, R²) en UI.
- Versionado de modelos y histórico.
- Curvas no lineales (piecewise / exponencial).
- Simulación Monte Carlo con probabilidad de Safety Car.
- Versionado de modelos y histórico.
## 11. Contribuir

1. Fork / rama feature.
2. Cambios con mensajes de commit claros (ES o EN).
3. PR describiendo: objetivo, cambios, pruebas manuales.
Sugerido:
## 12. Licencia
2. Cambios con mensajes de commit claros (ES o EN).
3. PR describiendo: objetivo, cambios, pruebas manuales.

## 13. Descargo de Responsabilidad
MIT – ver `LICENSE`.

## 13. Descargo de Responsabilidad
Este software se ofrece "tal cual", sin garantías. Uso bajo propia responsabilidad. No distribuye datos originales del juego.

---
¡Felices estrategias! 🏁
