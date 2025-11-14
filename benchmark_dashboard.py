#!/usr/bin/env python3
"""
Script de pruebas de rendimiento del dashboard de F1 Pitstop Strategy.

Este script mide el tiempo de carga y renderizado de diferentes componentes
del dashboard de Streamlit sin necesidad de ejecutar la interfaz gráfica.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import psutil

# Importar módulos del proyecto
try:
    from f1m.common import collect_practice_data
    from f1m.modeling import fit_degradation_model
    from f1m.planner import enumerate_plans
    from f1m.telemetry import optimize_dataframe_memory
except ImportError as e:
    print(f"Error importing modules: {e}")
    exit(1)


def get_memory_usage() -> float:
    """Obtiene el uso actual de memoria en MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # Convertir a MB


def time_function(func, *args, **kwargs) -> tuple:
    """Ejecuta una función y mide su tiempo de ejecución y uso de memoria."""
    start_time = time.time()
    start_memory = get_memory_usage()

    result = func(*args, **kwargs)

    end_time = time.time()
    end_memory = get_memory_usage()

    execution_time = end_time - start_time
    memory_delta = end_memory - start_memory

    return result, execution_time, memory_delta


def simulate_dashboard_data_loading() -> Dict[str, Any]:
    """Simula la carga de datos que haría el dashboard."""
    print("🔄 Simulando carga de datos del dashboard...")

    results = {}

    # Simular carga de datos de práctica (similar a lo que hace el dashboard)
    data_root = Path("logs_in/Bahrain")

    # Cargar datos para múltiples pilotos
    pilots = ["Fernando", "Lance"]
    all_data = []

    start_time = time.time()
    start_memory = get_memory_usage()

    for pilot in pilots:
        try:
            data, load_time, _ = time_function(
                collect_practice_data, data_root, "Bahrain", pilot
            )
            if not data.empty:
                all_data.append(data)
        except Exception as e:
            print(f"Warning: Could not load data for {pilot}: {e}")

    # Combinar datos
    if all_data:
        combined_data = pd.concat(all_data, ignore_index=True)
        combined_data, opt_time, _ = time_function(
            optimize_dataframe_memory, combined_data
        )
    else:
        combined_data = pd.DataFrame()

    end_time = time.time()
    end_memory = get_memory_usage()

    total_time = end_time - start_time
    memory_delta = end_memory - start_memory

    results["dashboard_data_loading"] = {
        "total_time_seconds": total_time,
        "memory_delta_mb": memory_delta,
        "pilots_loaded": len([p for p in pilots if any(not d.empty for d in all_data)]),
        "total_rows": len(combined_data),
        "description": "Carga de datos de práctica para múltiples pilotos con optimización",
    }

    return results


def simulate_model_fitting_workflow() -> Dict[str, Any]:
    """Simula el flujo de ajuste de modelos del dashboard."""
    print("🔄 Simulando ajuste de modelos del dashboard...")

    # Obtener datos de práctica
    data_root = Path("logs_in/Bahrain")
    practice_data, _, _ = time_function(
        collect_practice_data, data_root, "Bahrain", "Fernando"
    )

    if practice_data.empty:
        # Crear datos sintéticos si no hay datos reales
        practice_data = pd.DataFrame(
            {
                "compound": ["SOFT"] * 20 + ["MEDIUM"] * 20,
                "tire_age": list(range(1, 21)) + list(range(1, 21)),
                "lap_time_s": [
                    90.0 + 0.1 * i + np.random.normal(0, 0.5) for i in range(1, 21)
                ]
                + [92.0 + 0.08 * i + np.random.normal(0, 0.5) for i in range(1, 21)],
            }
        )

    # Ajustar modelos
    models, fit_time, memory_delta = time_function(fit_degradation_model, practice_data)

    results = {
        "model_fitting_workflow": {
            "data_rows": len(practice_data),
            "fitting_time_seconds": fit_time,
            "memory_delta_mb": memory_delta,
            "compounds_modeled": len(models),
            "description": "Flujo completo de ajuste de modelos desde datos de práctica",
        }
    }

    return results


def simulate_strategy_calculation() -> Dict[str, Any]:
    """Simula el cálculo de estrategias del dashboard."""
    print("🔄 Simulando cálculo de estrategias...")

    # Preparar datos
    practice_laps = pd.DataFrame(
        {
            "compound": ["SOFT"] * 10 + ["MEDIUM"] * 10,
            "tire_age": list(range(1, 11)) + list(range(1, 11)),
            "lap_time_s": [90.0 + 0.1 * i for i in range(1, 11)]
            + [92.0 + 0.08 * i for i in range(1, 11)],
        }
    )

    models = fit_degradation_model(practice_laps)

    # Parámetros de carrera
    race_laps = 30
    compounds = list(models.keys())
    pit_loss = 20.0

    # Calcular planes
    plans, calc_time, memory_delta = time_function(
        enumerate_plans,
        race_laps=race_laps,
        compounds=compounds,
        models=models,
        practice_laps=practice_laps,
        pit_loss=pit_loss,
        max_stops=2,
        top_k=3,
    )

    results = {
        "strategy_calculation": {
            "race_laps": race_laps,
            "compounds_available": len(compounds),
            "plans_calculated": len(plans),
            "calculation_time_seconds": calc_time,
            "memory_delta_mb": memory_delta,
            "description": f"Cálculo de estrategias para carrera de {race_laps} vueltas",
        }
    }

    return results


def run_dashboard_performance_tests() -> Dict[str, Any]:
    """Ejecuta pruebas de rendimiento específicas del dashboard."""
    print("🚀 Iniciando pruebas de rendimiento del dashboard F1 Pitstop")
    print("=" * 65)

    all_results = {}

    # Ejecutar cada simulación del dashboard
    dashboard_tests = [
        simulate_dashboard_data_loading,
        simulate_model_fitting_workflow,
        simulate_strategy_calculation,
    ]

    for test_func in dashboard_tests:
        try:
            results = test_func()
            all_results.update(results)
            print("✅ Completado\n")
        except Exception as e:
            print(f"❌ Error en {test_func.__name__}: {e}\n")
            all_results[test_func.__name__] = {"error": str(e)}

    return all_results


def print_dashboard_results(results: Dict[str, Any]):
    """Imprime los resultados de las pruebas del dashboard."""
    print("📊 RESULTADOS DE RENDIMIENTO DEL DASHBOARD")
    print("=" * 65)

    for test_name, test_results in results.items():
        if "error" in test_results:
            print(f"❌ {test_name}: ERROR - {test_results['error']}")
            continue

        print(f"✅ {test_name.upper().replace('_', ' ')}")
        print("-" * 50)

        for key, value in test_results.items():
            if key == "description":
                print(f"Descripción: {value}")
            elif "time" in key and "seconds" in key:
                print(".4f")
            elif "memory" in key and ("mb" in key or "MB" in key):
                print(".2f")
            elif isinstance(value, (int, float)) and any(
                word in key.lower()
                for word in ["rows", "laps", "calculated", "available", "loaded"]
            ):
                print(f"{key.replace('_', ' ').title()}: {value:,}")
            else:
                print(f"{key.replace('_', ' ').title()}: {value}")

        print()


def main():
    """Función principal."""
    results = run_dashboard_performance_tests()
    print_dashboard_results(results)

    # Resumen ejecutivo
    print("📈 RESUMEN EJECUTIVO - DASHBOARD")
    print("=" * 65)

    total_tests = len(results)
    successful_tests = sum(1 for r in results.values() if "error" not in r)

    print(f"Tests del dashboard ejecutados: {total_tests}")
    print(f"Tests exitosos: {successful_tests}")
    print(f"Tasa de éxito: {(successful_tests / total_tests) * 100:.1f}%")

    if successful_tests > 0:
        print("\n🎯 Métricas clave del dashboard:")
        if "dashboard_data_loading" in results:
            data_load = results["dashboard_data_loading"]
            print(
                f"  • Carga de datos: {data_load['total_time_seconds']:.4f}s para {data_load['total_rows']:,} filas"
            )
        if "model_fitting_workflow" in results:
            model_fit = results["model_fitting_workflow"]
            print(
                f"  • Ajuste de modelos: {model_fit['fitting_time_seconds']:.4f}s para {model_fit['compounds_modeled']} compuestos"
            )
        if "strategy_calculation" in results:
            strategy = results["strategy_calculation"]
            print(
                f"  • Cálculo de estrategias: {strategy['calculation_time_seconds']:.4f}s para {strategy['race_laps']} vueltas"
            )


if __name__ == "__main__":
    main()
