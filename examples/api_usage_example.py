#!/usr/bin/env python3
"""
Ejemplo de uso de la API de F1 Pitstop Strategy.

Este script demuestra cómo usar las funciones principales del paquete f1m
para analizar datos de telemetría de F1 Manager 2024.
"""

import sys
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

# Core module imports with fallback for sys.path manipulation
try:
    from f1m.modeling import fit_degradation_model
    from f1m.planner import enumerate_plans
    from f1m.telemetry import build_lap_summary, build_stints, load_session_csv
except ImportError:
    # Add project root to sys.path if direct import fails
    _project_root = Path(__file__).resolve().parents[1]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    try:
        from f1m.modeling import fit_degradation_model
        from f1m.planner import enumerate_plans
        from f1m.telemetry import build_lap_summary, build_stints, load_session_csv
    except ImportError as e:
        raise ImportError(
            f"No se pudieron importar módulos de f1m. Asegúrate que f1m está en el PYTHONPATH. Error: {e}"
        ) from e


def ejemplo_analisis_basico():
    """Ejemplo de análisis básico de telemetría."""
    print("=== Análisis Básico de Telemetría ===")

    # Ruta a un archivo CSV de ejemplo
    csv_path = Path(
        "logs_in/exported_data/Bahrain/Practice 1/Fernando Alonso/telemetry.csv"
    )

    if not csv_path.exists():
        print(f"Archivo no encontrado: {csv_path}")
        print("Asegúrate de tener datos exportados de F1 Manager 2024")
        return

    # Cargar datos
    df = load_session_csv(csv_path)
    print(f"Datos cargados: {len(df)} filas")

    # Construir resumen de vueltas
    laps = build_lap_summary(df)
    print(f"Vueltas analizadas: {len(laps)}")

    # Detectar stints
    stints = build_stints(laps)
    print(f"Stints detectados: {len(stints)}")

    # Mostrar estadísticas básicas
    if not laps.empty and "lap_time_s" in laps.columns:
        print(f"Tiempo mínimo: {laps['lap_time_s'].min():.2f}s")
        print(f"Tiempo promedio: {laps['lap_time_s'].mean():.2f}s")


def ejemplo_metricas_modelo():
    """Ejemplo de cálculo de métricas del modelo."""
    print("\n=== Métricas del Modelo ===")

    # Usar datos mock para ejemplo
    practice_data = pd.DataFrame(
        {
            "compound": ["SOFT"] * 10 + ["MEDIUM"] * 10,
            "tire_age": list(range(10)) * 2,
            "lap_time_s": [94.3 + 0.145 * i for i in range(10)]
            + [95.1 + 0.120 * i for i in range(10)],
        }
    )

    models = fit_degradation_model(practice_data)
    print(f"Modelos ajustados: {len(models)}")

    # Calcular métricas (simulando la función del dashboard)
    for compound, params in models.items():
        if len(params) >= 2:
            compound_data = practice_data[practice_data["compound"] == compound]
            if not compound_data.empty:
                intercept, slope = params[0], params[1]
                predictions = intercept + slope * compound_data["tire_age"]
                actual = compound_data["lap_time_s"]

                mae = abs(predictions - actual).mean()
                ss_res = ((actual - predictions) ** 2).sum()
                ss_tot = ((actual - actual.mean()) ** 2).sum()
                r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

                print(f"{compound}: MAE={mae:.3f}s, R²={r2:.3f}")


def ejemplo_planificacion():
    """Ejemplo de planificación de estrategia."""
    print("\n=== Planificación de Estrategia ===")

    # Parámetros de ejemplo
    race_laps = 57  # Bahrain Grand Prix
    compounds = ["SOFT", "MEDIUM", "HARD"]
    models: Dict[str, Tuple[float, float]] = {
        "SOFT": (94.3, 0.145),
        "MEDIUM": (95.1, 0.120),
        "HARD": (96.0, 0.095),
    }
    pit_loss = 20.0  # segundos

    # Datos de práctica (usar datos mock para ejemplo)
    practice_data = pd.DataFrame(
        {
            "compound": ["SOFT"] * 10 + ["MEDIUM"] * 10,
            "tire_age": list(range(10)) * 2,
            "lap_time_s": [94.3 + 0.145 * i for i in range(10)]
            + [95.1 + 0.120 * i for i in range(10)],
        }
    )

    # Generar planes
    plans = enumerate_plans(
        race_laps,
        compounds,
        models,
        practice_data,
        pit_loss,
        top_k=5,
    )

    print(f"Planes generados: {len(plans)}")
    for i, plan in enumerate(plans[:3], 1):
        print(f"Plan {i}: Tiempo total = {plan['total_time']:.2f}s")
        print(f"  Stints: {plan['stints']}")


def main():
    """Función principal del ejemplo."""
    print("🚗 F1 Pitstop Strategy - Ejemplos de Uso")
    print("=" * 50)

    ejemplo_analisis_basico()
    ejemplo_metricas_modelo()
    ejemplo_planificacion()

    print("\n" + "=" * 50)
    print("✅ Ejemplos completados")
    print("\nPara más información, consulta la documentación en README.md")


if __name__ == "__main__":
    main()
