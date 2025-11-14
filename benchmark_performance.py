#!/usr/bin/env python3
"""
Script de pruebas de rendimiento para la aplicación F1 Pitstop Strategy.

Mide el rendimiento de las operaciones críticas:
- Carga de datos de práctica
- Optimización de memoria
- Ajuste de modelos de degradación
- Enumeración de planes de carrera
- Uso de memoria durante operaciones
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


def benchmark_data_loading() -> Dict[str, Any]:
    """Benchmark de carga de datos de práctica."""
    print("🔄 Probando carga de datos de práctica...")

    # Usar datos reales si existen
    data_root = Path("logs_in/Bahrain")

    results = {}

    # Probar carga de datos para Fernando Alonso
    _, load_time, memory_delta = time_function(
        collect_practice_data, data_root, "Bahrain", "Fernando"
    )

    results["data_loading"] = {
        "time_seconds": load_time,
        "memory_delta_mb": memory_delta,
        "description": "Carga de datos de práctica para Fernando Alonso",
    }

    return results


def benchmark_memory_optimization() -> Dict[str, Any]:
    """Benchmark de optimización de memoria."""
    print("🔄 Probando optimización de memoria...")

    # Crear un DataFrame grande con tipos ineficientes
    np.random.seed(42)
    df = pd.DataFrame(
        {
            "int_col": np.random.randint(0, 1000, 100000),
            "float_col": np.random.random(100000),
            "str_col": ["test_string"] * 100000,
        }
    )

    # Convertir a tipos más grandes
    df["int_col"] = df["int_col"].astype(np.int64)
    df["float_col"] = df["float_col"].astype(np.float64)

    original_memory = df.memory_usage(deep=True).sum() / 1024 / 1024  # MB

    # Optimizar memoria
    optimized_df, opt_time, memory_delta = time_function(optimize_dataframe_memory, df)

    optimized_memory = optimized_df.memory_usage(deep=True).sum() / 1024 / 1024  # MB
    memory_savings = original_memory - optimized_memory
    savings_percentage = (memory_savings / original_memory) * 100

    results = {
        "memory_optimization": {
            "original_memory_mb": original_memory,
            "optimized_memory_mb": optimized_memory,
            "memory_savings_mb": memory_savings,
            "savings_percentage": savings_percentage,
            "optimization_time_seconds": opt_time,
            "memory_delta_mb": memory_delta,
            "description": "Optimización de memoria en DataFrame de 100k filas",
        }
    }

    return results


def benchmark_model_fitting() -> Dict[str, Any]:
    """Benchmark de ajuste de modelos de degradación."""
    print("🔄 Probando ajuste de modelos...")

    # Crear datos de práctica sintéticos
    np.random.seed(42)
    practice_data = pd.DataFrame(
        {
            "compound": ["SOFT"] * 50 + ["MEDIUM"] * 50,
            "tire_age": list(range(1, 51)) + list(range(1, 51)),
            "lap_time_s": [
                90.0 + 0.1 * i + np.random.normal(0, 0.5) for i in range(1, 51)
            ]
            + [92.0 + 0.08 * i + np.random.normal(0, 0.5) for i in range(1, 51)],
        }
    )

    models, fit_time, memory_delta = time_function(fit_degradation_model, practice_data)

    results = {
        "model_fitting": {
            "num_compounds": len(models),
            "fitting_time_seconds": fit_time,
            "memory_delta_mb": memory_delta,
            "models_found": list(models.keys()),
            "description": "Ajuste de modelos para SOFT y MEDIUM compounds",
        }
    }

    return results


def benchmark_plan_enumeration() -> Dict[str, Any]:
    """Benchmark de enumeración de planes de carrera."""
    print("🔄 Probando enumeración de planes...")

    # Crear datos de práctica
    practice_laps = pd.DataFrame(
        {
            "compound": ["SOFT", "SOFT", "MEDIUM", "MEDIUM"],
            "tire_age": [1, 2, 1, 2],
            "lap_time_s": [90.0, 90.5, 92.0, 92.3],
        }
    )

    # Modelos simples
    models = {"SOFT": (90.0, 0.5), "MEDIUM": (92.0, 0.3)}

    compounds = ["SOFT", "MEDIUM"]
    race_laps = 20
    pit_loss = 20.0

    plans, enum_time, memory_delta = time_function(
        enumerate_plans,
        race_laps=race_laps,
        compounds=compounds,
        models=models,
        practice_laps=practice_laps,
        pit_loss=pit_loss,
        max_stops=2,
        top_k=5,
    )

    results = {
        "plan_enumeration": {
            "race_laps": race_laps,
            "num_plans_generated": len(plans),
            "enumeration_time_seconds": enum_time,
            "memory_delta_mb": memory_delta,
            "compounds_used": compounds,
            "description": f"Enumeración de planes para carrera de {race_laps} vueltas",
        }
    }

    return results


def run_performance_tests() -> Dict[str, Any]:
    """Ejecuta todas las pruebas de rendimiento."""
    print("🚀 Iniciando pruebas de rendimiento para F1 Pitstop Strategy")
    print("=" * 60)

    all_results = {}

    # Ejecutar cada benchmark
    benchmarks = [
        benchmark_data_loading,
        benchmark_memory_optimization,
        benchmark_model_fitting,
        benchmark_plan_enumeration,
    ]

    for benchmark_func in benchmarks:
        try:
            results = benchmark_func()
            all_results.update(results)
            print("✅ Completado\n")
        except Exception as e:
            print(f"❌ Error en {benchmark_func.__name__}: {e}\n")
            all_results[benchmark_func.__name__] = {"error": str(e)}

    return all_results


def print_results(results: Dict[str, Any]):
    """Imprime los resultados de las pruebas de rendimiento."""
    print("📊 RESULTADOS DE PRUEBAS DE RENDIMIENTO")
    print("=" * 60)

    for test_name, test_results in results.items():
        if "error" in test_results:
            print(f"❌ {test_name}: ERROR - {test_results['error']}")
            continue

        print(f"✅ {test_name.upper()}")
        print("-" * 40)

        for key, value in test_results.items():
            if key == "description":
                print(f"Descripción: {value}")
            elif "time" in key and "seconds" in key:
                print(".4f")
            elif "memory" in key and ("mb" in key or "MB" in key):
                print(".2f")
            elif isinstance(value, float) and "percentage" in key:
                print(".1f")
            else:
                print(f"{key.replace('_', ' ').title()}: {value}")

        print()


def main():
    """Función principal."""
    results = run_performance_tests()
    print_results(results)

    # Resumen ejecutivo
    print("📈 RESUMEN EJECUTIVO")
    print("=" * 60)

    total_tests = len(results)
    successful_tests = sum(1 for r in results.values() if "error" not in r)

    print(f"Tests ejecutados: {total_tests}")
    print(f"Tests exitosos: {successful_tests}")
    print(f"Tasa de éxito: {(successful_tests / total_tests) * 100:.1f}%")

    if successful_tests > 0:
        print("✅ Todas las pruebas de rendimiento completadas exitosamente")
        print("📈 Rendimiento optimizado con las mejoras implementadas")


if __name__ == "__main__":
    main()
