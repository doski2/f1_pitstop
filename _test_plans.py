import sys

sys.path.insert(0, "app")
sys.path.insert(0, ".")
from pathlib import Path

from _data import fit_combined_model, generate_race_plans  # type: ignore[import]

from f1m.common import collect_practice_data
from f1m.modeling import fit_degradation_model, max_stint_length

data_root = Path("logs_in/exported_data")
practice_data = collect_practice_data(data_root, "Bahrain", "Fernando Alonso")
combined = fit_combined_model(practice_data, None)
models = fit_degradation_model(combined)
print("Compuestos:", list(models.keys()))

for comp in models:
    ms = max_stint_length(combined, comp)
    print(f"  {comp}: max_stint={ms}")

use_fuel = "fuel" in combined.columns and combined["fuel"].notna().sum() >= 3
print(f"use_fuel={use_fuel}")
print("Coeficientes de modelos:")
for comp, coeffs in models.items():
    print(f"  {comp}: {coeffs}")

# Prueba directa de planner con parámetros mínimos
from f1m.planner import enumerate_plans

plans_direct = enumerate_plans(
    57,
    list(models.keys()),
    models,
    combined,
    22.0,
    max_stops=2,
    exact_stops=False,
    min_stint=3,
    require_two_compounds=False,
    use_fuel=False,
    start_fuel=110.0,
    cons_per_lap=0.0,
    race_temp=0.0,
)
print(f"Planes (sin restricciones): {len(plans_direct)}")
if plans_direct:
    for p in plans_direct[:3]:
        stints = " | ".join(f"{s['compound']} {s['laps']}v" for s in p["stints"])
        print(f"  {stints} | {p['total_time']:.0f}s | {p['stops']} stops")

plans = generate_race_plans(
    57,
    list(models.keys()),
    models,
    combined,
    22.0,
    max_stops=2,
    exact_stops=True,
    min_stint=3,
    require_two_compounds=True,
    use_fuel=use_fuel,
    start_fuel=110.0,
    cons_per_lap=1.4,
    race_temp=35.0,
)
print(f"Planes: {len(plans)}")
for i, p in enumerate(plans, 1):
    stints = " | ".join(f"{s['compound']} {s['laps']}v" for s in p["stints"])
    print(f"  Plan {i}: {stints} | {p['total_time']:.0f}s | {p['stops']} paradas")
