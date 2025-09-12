"""Planificador:
- `enumerate_plans`: backtracking para enumerar planes (stints) con límites.
- `live_pit_recommendation`: ventana local que sugiere vuelta de parada y compuesto.
Incluye chequeos de viabilidad por combustible cuando hay modelo con fuel.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .modeling import max_stint_length, stint_time


def enumerate_plans(
    race_laps: int,
    compounds: List[str],
    models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]],
    practice_laps: pd.DataFrame,
    pit_loss: float,
    max_stops: int = 2,
    min_stint: int = 5,
    require_two_compounds: bool = True,
    top_k: int = 3,
    use_fuel: bool = False,
    start_fuel: float = 0.0,
    cons_per_lap: float = 0.0,
) -> List[dict]:
    """Devuelve los `top_k` mejores planes por tiempo total estimado.

    The plan is a list of (compound, laps) stints whose laps sum to ``race_laps``.
    This function validates fuel feasibility when ``use_fuel`` is enabled and uses
    ``stint_time`` to compute expected stint durations.
    """

    plans: List[dict] = []
    max_len = {c: max_stint_length(practice_laps, c) for c in compounds}

    def add_plan(seq: List[Tuple[str, int]]):
        # total laps must match
        if sum(laps for _, laps in seq) != race_laps:
            return
        if require_two_compounds and len({c for c, _ in seq}) < 2 and race_laps > 15:
            return
        total = 0.0
        details: List[dict] = []
        fuel_cursor = start_fuel
        for comp, laps in seq:
            if comp not in models:
                return
            coeffs = models[comp]
            # fuel-aware model: (a, b_age, c_fuel)
            if use_fuel and len(coeffs) == 3:
                a, b_age, c_fuel = coeffs
                ages = np.arange(0, laps)
                fuel_series = fuel_cursor - cons_per_lap * ages
                if (fuel_series < 0).any():
                    return
                stint_time_val = float(np.sum(a + b_age * ages + c_fuel * fuel_series))
                fuel_cursor -= cons_per_lap * laps
            else:
                a, b_age = coeffs[0], coeffs[1]
                stint_time_val = stint_time(a, b_age, laps)
            total += stint_time_val
            details.append({"compound": comp, "laps": laps, "pred_time": stint_time_val})
        total += pit_loss * (len(seq) - 1)
        plans.append({"stints": details, "total_time": total, "stops": len(seq) - 1})

    def recurse(remaining: int, current: List[Tuple[str, int]], depth: int):
        if remaining == 0:
            add_plan(current)
            return
        if depth > max_stops:
            return
        for comp in compounds:
            max_l = min(max_len.get(comp, remaining), remaining)
            for laps in range(min_stint, max_l + 1):
                if remaining - laps != 0 and remaining - laps < min_stint:
                    continue
                recurse(remaining - laps, current + [(comp, laps)], depth + 1)

    recurse(race_laps, [], 0)
    plans.sort(key=lambda x: x["total_time"])
    return plans[:top_k]


def live_pit_recommendation(
    current_lap: int,
    total_race_laps: int,
    current_compound: str,
    current_tire_age: int,
    models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]],
    practice_laps: pd.DataFrame,
    pit_loss: float,
    window: int = 12,
    use_fuel: bool = False,
    current_fuel: float = 0.0,
    cons_per_lap: float = 0.0,
) -> Optional[dict]:
    """Recommend whether to pit now and which compound to fit for the remainder.

    Returns a dict with keys: ``pit_on_lap``, ``continue_laps``, ``new_compound``,
    ``projected_total_remaining`` or ``None`` if no viable recommendation.
    """

    if not models or current_compound not in models:
        return None
    rem_laps = total_race_laps - current_lap
    if rem_laps <= 0:
        return None
    cur_coeffs = models[current_compound]
    if use_fuel and len(cur_coeffs) == 3:
        a_cur, b_cur, c_cur = cur_coeffs
    else:
        a_cur, b_cur = cur_coeffs[0], cur_coeffs[1]
        c_cur = None

    evaluations: List[dict] = []
    for pit_in in range(1, min(window, rem_laps) + 1):
        ages = np.arange(current_tire_age, current_tire_age + pit_in)
        if use_fuel and c_cur is not None:
            fuel_seg = current_fuel - cons_per_lap * np.arange(0, pit_in)
            if (fuel_seg < 0).any():
                continue
            time_current = float(np.sum(a_cur + b_cur * ages + c_cur * fuel_seg))
            fuel_after = current_fuel - cons_per_lap * pit_in
        else:
            time_current = float(np.sum(a_cur + b_cur * ages))
            fuel_after = current_fuel - cons_per_lap * pit_in
        laps_after = rem_laps - pit_in
        if laps_after < 0:
            continue
        best_comp_alt: Optional[str] = None
        best_tail_time: Optional[float] = None
        for comp, coeffs in models.items():
            if use_fuel and len(coeffs) == 3:
                a_new, b_new, c_new = coeffs
                new_ages = np.arange(0, laps_after)
                if laps_after > 0:
                    fuel_new = fuel_after - cons_per_lap * new_ages
                    if (fuel_new < 0).any():
                        continue
                    time_new = float(np.sum(a_new + b_new * new_ages + c_new * fuel_new))
                else:
                    time_new = 0.0
            else:
                a_new, b_new = coeffs[0], coeffs[1]
                time_new = stint_time(a_new, b_new, laps_after)
            if best_tail_time is None or time_new < best_tail_time:
                best_tail_time = time_new
                best_comp_alt = comp
        if best_comp_alt is None or best_tail_time is None:
            continue
        total = time_current + pit_loss + best_tail_time
        evaluations.append(
            {
                "pit_on_lap": current_lap + pit_in,
                "continue_laps": pit_in,
                "new_compound": best_comp_alt,
                "projected_total_remaining": total,
            }
        )
    if not evaluations:
        return None
    return min(evaluations, key=lambda x: x["projected_total_remaining"])
