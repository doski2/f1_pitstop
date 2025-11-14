"""Planificador:
- `enumerate_plans`: backtracking para enumerar planes (stints) con límites.
- `live_pit_recommendation`: ventana local que sugiere vuelta de parada y compuesto.
Incluye chequeos de viabilidad por combustible cuando hay modelo con fuel.
"""

from __future__ import annotations

from functools import lru_cache

from .imports import (
    DEFAULT_CONS_PER_LAP,
    DEFAULT_MAX_STOPS,
    DEFAULT_MIN_STINT,
    DEFAULT_START_FUEL,
    DEFAULT_TOP_K_PLANS,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
    np,
    pd,
)
from .modeling import adjust_lap_time_for_conditions, max_stint_length, stint_time


def enumerate_plans(
    race_laps: int,
    compounds: List[str],
    models: Mapping[str, Union[Tuple[float, float], Tuple[float, float, float]]],
    practice_laps: pd.DataFrame,
    pit_loss: float,
    max_stops: int = DEFAULT_MAX_STOPS,
    min_stint: int = DEFAULT_MIN_STINT,
    require_two_compounds: bool = True,
    top_k: int = DEFAULT_TOP_K_PLANS,
    use_fuel: bool = False,
    start_fuel: float = DEFAULT_START_FUEL,
    cons_per_lap: float = DEFAULT_CONS_PER_LAP,
    safety_car_percentage: float = 0.0,
    rain_percentage: float = 0.0,
) -> List[dict]:
    """Devuelve los `top_k` mejores planes por tiempo total estimado.

    The plan is a list of (compound, laps) stints whose laps sum to ``race_laps``.
    This function validates fuel feasibility when ``use_fuel`` is enabled and uses
    ``stint_time`` to compute expected stint durations.

    Optimized with memoization to avoid exponential recursion.
    """

    plans: List[dict] = []
    max_len = {c: max_stint_length(practice_laps, c) for c in compounds}

    @lru_cache(maxsize=None)
    def compute_stint_time(
        comp: str, laps: int, fuel_cursor: float
    ) -> Tuple[float, float]:
        """Compute stint time and updated fuel. Memoized for performance."""
        if comp not in models:
            return float("inf"), fuel_cursor
        coeffs = models[comp]
        if use_fuel and len(coeffs) == 3:
            a, b_age, c_fuel = coeffs
            ages = np.arange(0, laps)
            fuel_series = fuel_cursor - cons_per_lap * ages
            if (fuel_series < 0).any():
                return float("inf"), fuel_cursor
            stint_time_val = float(np.sum(a + b_age * ages + c_fuel * fuel_series))
            new_fuel = fuel_cursor - cons_per_lap * laps
        else:
            a, b_age = coeffs[0], coeffs[1]
            stint_time_val = stint_time(a, b_age, laps)
            new_fuel = fuel_cursor - cons_per_lap * laps

        # Apply adjustments for Safety Car and rain conditions
        # Assume conditions apply to a percentage of laps in the stint
        safety_car_laps = int(laps * safety_car_percentage)
        rain_laps = int(laps * rain_percentage)
        normal_laps = laps - safety_car_laps - rain_laps

        # Calculate adjusted time
        adjusted_time = (
            normal_laps * (stint_time_val / laps)
            + safety_car_laps
            * adjust_lap_time_for_conditions(stint_time_val / laps, safety_car=True)
            + rain_laps
            * adjust_lap_time_for_conditions(stint_time_val / laps, rain=True)
        )

        return adjusted_time, new_fuel

    def generate_plans_dp(
        remaining: int,
        stops_used: int,
        last_comp: str,
        fuel_level: float,
        compounds_used: frozenset,
    ) -> List[Tuple[List[Tuple[str, int]], float, float]]:
        """Generate all valid plans for remaining laps using DP with memoization."""
        # Cache key: (remaining, stops_used, last_comp, fuel_level_rounded, compounds_used)
        fuel_key = round(fuel_level, 1)  # Round fuel to 0.1 precision for caching
        cache_key = (remaining, stops_used, last_comp, fuel_key, compounds_used)

        if cache_key in _plan_cache:
            return _plan_cache[cache_key]

        if remaining == 0:
            # Valid plan found
            result: List[Tuple[List[Tuple[str, int]], float, float]] = [([], 0.0, fuel_level)]
            _plan_cache[cache_key] = result
            return result

        if stops_used > max_stops:
            _plan_cache[cache_key] = []
            return []

        results = []

        for comp in compounds:
            if comp == last_comp and stops_used > 0:
                # Avoid consecutive same compound unless it's the first stint
                continue

            max_l = min(max_len.get(comp, remaining), remaining)
            min_laps = min_stint if remaining > min_stint else remaining

            for laps in range(min_laps, max_l + 1):
                if remaining - laps > 0 and remaining - laps < min_stint:
                    continue

                stint_time_val, new_fuel = compute_stint_time(comp, laps, fuel_level)
                if stint_time_val == float("inf"):
                    continue  # Fuel constraint violated

                new_compounds_used = compounds_used | {comp}

                # Recursive call for remaining laps
                sub_plans = generate_plans_dp(
                    remaining - laps,
                    stops_used + (1 if stops_used > 0 or last_comp != "" else 0),
                    comp,
                    new_fuel,
                    new_compounds_used,
                )

                for sub_stints, sub_time, final_fuel in sub_plans:
                    total_time = stint_time_val + sub_time
                    new_stints = [(comp, laps)] + sub_stints
                    results.append((new_stints, total_time, final_fuel))

        # Keep only top results to limit memory usage
        results.sort(key=lambda x: x[1])  # Sort by total time
        results = results[: top_k * 2]  # Keep more than needed for combination

        _plan_cache[cache_key] = results
        return results

    # Global cache for this function call
    _plan_cache: Dict[Tuple[int, int, str, float, frozenset], List] = {}

    # Generate all plans starting with empty state
    all_plans = generate_plans_dp(race_laps, 0, "", start_fuel, frozenset())

    # Convert to the expected format
    for stints, total_time, final_fuel in all_plans:
        if not stints:
            continue

        # Check two-compound requirement
        if (
            require_two_compounds
            and len(set(c for c, _ in stints)) < 2
            and race_laps > 15
        ):
            continue

        # Add pit stop losses
        stops = len(stints) - 1
        total_time_with_pits = total_time + pit_loss * stops

        details = []
        for comp, laps in stints:
            coeffs = models[comp]
            if use_fuel and len(coeffs) == 3:
                a, b_age, c_fuel = coeffs
                ages = np.arange(0, laps)
                fuel_series = start_fuel - cons_per_lap * ages
                pred_time = float(np.sum(a + b_age * ages + c_fuel * fuel_series))
            else:
                a, b_age = coeffs[0], coeffs[1]
                pred_time = stint_time(a, b_age, laps)
            details.append({"compound": comp, "laps": laps, "pred_time": pred_time})

        plans.append(
            {"stints": details, "total_time": total_time_with_pits, "stops": stops}
        )

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
                    time_new = float(
                        np.sum(a_new + b_new * new_ages + c_new * fuel_new)
                    )
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
    best = evaluations[0]
    best_val = (
        float(best["projected_total_remaining"])
        if isinstance(best.get("projected_total_remaining"), (int, float))
        else float(best["projected_total_remaining"])
    )
    for ev in evaluations[1:]:
        try:
            v = float(ev["projected_total_remaining"])
        except (ValueError, TypeError):
            continue
        if v < best_val:
            best_val = v
            best = ev
    return best
