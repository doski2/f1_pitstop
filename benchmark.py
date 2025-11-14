#!/usr/bin/env python3
"""Benchmark script for F1 Pitstop performance analysis."""

import time
from pathlib import Path

from f1m.common import collect_practice_data
from f1m.modeling import fit_degradation_model
from f1m.planner import enumerate_plans
from f1m.telemetry import build_lap_summary, build_stints, load_session_csv


def benchmark_function(func, *args, **kwargs):
    """Benchmark a function by running it multiple times and averaging."""
    runs = 5
    times = []
    for _ in range(runs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        times.append(end - start)
    avg_time = sum(times) / len(times)
    return avg_time, result


def main():
    print("Iniciando benchmarks de rendimiento para F1 Pitstop...")

    # Usar datos de ejemplo
    data_root = Path("curated")
    track = "track=Bahrain"
    driver = "driver=14_Fernando_Alonso"

    # Benchmark 1: Cargar datos de práctica
    print("\n1. Benchmark: collect_practice_data")
    time_taken, practice_data = benchmark_function(
        collect_practice_data, data_root, track, driver
    )
    print(".4f")
    print(f"   Filas cargadas: {len(practice_data)}")

    # Benchmark 2: Ajustar modelo de degradación
    print("\n2. Benchmark: fit_degradation_model")
    time_taken, model = benchmark_function(fit_degradation_model, practice_data)
    print(".4f")
    print(f"   Modelos ajustados: {len(model)}")

    # Benchmark 3: Cargar CSV de sesión (usar un archivo CSV si existe)
    csv_path = Path(
        "logs_in/exported_data/Bahrain/Practice 1/Fernando Alonso/2025-08-24_01-15-07_AstonMartin2_Telemetry_Bahrain_Practice 1.csv"
    )
    if csv_path.exists():
        print("\n3. Benchmark: load_session_csv")
        time_taken, df = benchmark_function(load_session_csv, csv_path)
        print(".4f")
        print(f"   Filas cargadas: {len(df)}")

        # Benchmark 4: Construir resumen de vueltas
        print("\n4. Benchmark: build_lap_summary")
        time_taken, lap_summary = benchmark_function(build_lap_summary, df)
        print(".4f")
        print(f"   Vueltas resumidas: {len(lap_summary)}")

        # Benchmark 5: Construir stints
        print("\n5. Benchmark: build_stints")
        time_taken, stints = benchmark_function(build_stints, lap_summary)
        print(".4f")
        print(f"   Stints detectados: {len(stints)}")
    else:
        print("\n3-5. Benchmarks de telemetría omitidos: archivo CSV no encontrado")

    # Benchmark 6: Enumerar planes de pits (omitido si no hay datos de práctica)
    if not practice_data.empty:
        print("\n6. Benchmark: enumerate_plans (simulado)")
        models = {"SOFT": (100.0, 0.1), "MEDIUM": (105.0, 0.08)}
        time_taken, plans = benchmark_function(
            enumerate_plans, 20, ["SOFT", "MEDIUM"], models, practice_data, 20.0
        )
        print(".4f")
        print(f"   Planes generados: {len(plans)}")
    else:
        print("\n6. Benchmark: enumerate_plans omitido (no hay datos de práctica)")

    print("\nBenchmarks completados.")


if __name__ == "__main__":
    main()
