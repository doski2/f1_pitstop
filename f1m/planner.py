"""Planificador:
- `enumerate_plans`: backtracking para enumerar planes (stints) con límites.
- `live_pit_recommendation`: ventana local que sugiere vuelta de parada y compuesto.
Incluye chequeos de viabilidad por combustible cuando hay modelo con fuel.
"""

from __future__ import annotations

from functools import lru_cache

from .common import canonical_compound, display_compound
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
    models: Mapping[str, Union[Tuple[float, float], Tuple[float, float, float], Tuple[float, float, float, float]]],
    practice_laps: pd.DataFrame,
    pit_loss: float,
    max_stops: int = DEFAULT_MAX_STOPS,
    exact_stops: bool = True,
    min_stint: int = DEFAULT_MIN_STINT,
    require_two_compounds: bool = True,
    top_k: int = DEFAULT_TOP_K_PLANS,
    use_fuel: bool = False,
    start_fuel: float = DEFAULT_START_FUEL,
    cons_per_lap: float = DEFAULT_CONS_PER_LAP,
    safety_car_percentage: float = 0.0,
    rain_percentage: float = 0.0,
    race_temp: float = 0.0,
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
        if len(coeffs) == 4:
            a, b_age, c_fuel, d_temp = coeffs
            a_eff = a + d_temp * race_temp
            ages = np.arange(0, laps)
            if use_fuel and c_fuel != 0.0:
                fuel_series = fuel_cursor - cons_per_lap * ages
                if (fuel_series < 0).any():
                    return float("inf"), fuel_cursor
                stint_time_val = float(np.sum(a_eff + b_age * ages + c_fuel * fuel_series))
            else:
                stint_time_val = stint_time(a_eff, b_age, laps)
            new_fuel = fuel_cursor - cons_per_lap * laps
        elif use_fuel and len(coeffs) == 3:
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
            result: List[Tuple[List[Tuple[str, int]], float, float]] = [
                ([], 0.0, fuel_level)
            ]
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
            if len(coeffs) == 4:
                a, b_age, c_fuel, d_temp = coeffs
                a_eff = a + d_temp * race_temp
                ages = np.arange(0, laps)
                if use_fuel and c_fuel != 0.0:
                    fuel_series = start_fuel - cons_per_lap * ages
                    pred_time = float(np.sum(a_eff + b_age * ages + c_fuel * fuel_series))
                else:
                    pred_time = stint_time(a_eff, b_age, laps)
            elif use_fuel and len(coeffs) == 3:
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

    if exact_stops:
        plans = [p for p in plans if p["stops"] == max_stops]
    plans.sort(key=lambda x: x["total_time"])
    return plans[:top_k]


def live_pit_recommendation(
    current_lap: int,
    total_race_laps: int,
    current_compound: str,
    current_tire_age: int,
    models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float], Tuple[float, float, float, float]]],
    practice_laps: pd.DataFrame,
    pit_loss: float,
    window: int = 12,
    use_fuel: bool = False,
    current_fuel: float = 0.0,
    cons_per_lap: float = 0.0,
    race_temp: float = 0.0,
) -> Optional[dict]:
    """Recommend whether to pit now and which compound to fit for the remainder.

    Returns a dict with keys: ``pit_on_lap``, ``continue_laps``, ``new_compound``,
    ``projected_total_remaining`` or ``None`` if no viable recommendation.
    """
    # Normalise the raw compound (e.g. "C3") to its canonical key (e.g. "Soft")
    # so it matches the keys produced by fit_degradation_model().
    current_compound = canonical_compound(current_compound)

    if not models or current_compound not in models:
        return None
    rem_laps = total_race_laps - current_lap
    if rem_laps <= 0:
        return None
    cur_coeffs = models[current_compound]
    if len(cur_coeffs) == 4:
        _a, _b, _c_fuel, _d_temp = cur_coeffs
        a_cur = _a + _d_temp * race_temp
        b_cur = _b
        c_cur = _c_fuel if use_fuel and _c_fuel != 0.0 else None
    elif use_fuel and len(cur_coeffs) == 3:
        a_cur, b_cur, c_cur = cur_coeffs
    else:
        a_cur, b_cur = cur_coeffs[0], cur_coeffs[1]
        c_cur = None

    evaluations: List[dict] = []
    for pit_in in range(1, min(window, rem_laps) + 1):
        ages = np.arange(current_tire_age, current_tire_age + pit_in)
        try:
            if use_fuel and c_cur is not None:
                fuel_seg = current_fuel - cons_per_lap * np.arange(0, pit_in)
                if (fuel_seg < 0).any():
                    continue
                time_current = float(np.sum(a_cur + b_cur * ages + c_cur * fuel_seg))
                fuel_after = current_fuel - cons_per_lap * pit_in
            else:
                time_current = float(np.sum(a_cur + b_cur * ages))
                fuel_after = current_fuel - cons_per_lap * pit_in
        except (ValueError, TypeError, RuntimeError):
            # Skip this pit window if any calculation error occurs
            continue
        laps_after = rem_laps - pit_in
        if laps_after < 0:
            continue
        best_comp_alt: Optional[str] = None
        best_tail_time: Optional[float] = None
        for comp, coeffs in models.items():
            try:
                if len(coeffs) == 4:
                    _a_n, _b_n, _c_n, _d_n = coeffs
                    a_new_eff = _a_n + _d_n * race_temp
                    new_ages = np.arange(0, laps_after)
                    if laps_after > 0:
                        if use_fuel and _c_n != 0.0:
                            fuel_new = fuel_after - cons_per_lap * new_ages
                            if (fuel_new < 0).any():
                                continue
                            time_new = float(
                                np.sum(a_new_eff + _b_n * new_ages + _c_n * fuel_new)
                            )
                        else:
                            time_new = stint_time(a_new_eff, _b_n, laps_after)
                    else:
                        time_new = 0.0
                elif use_fuel and len(coeffs) == 3:
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
            except (ValueError, TypeError, RuntimeError, IndexError):
                # Skip this compound if calculation fails
                continue
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
    best_val = float(best["projected_total_remaining"])
    for ev in evaluations[1:]:
        try:
            v = float(ev["projected_total_remaining"])
        except (ValueError, TypeError):
            continue
        if v < best_val:
            best_val = v
            best = ev
    return best


def plan_aware_recommendation(
    current_lap: int,
    total_race_laps: int,
    current_compound: str,
    current_tire_age: int,
    models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float], Tuple[float, float, float, float]]],
    chosen_plan: List[dict],
    practice_laps: pd.DataFrame,
    pit_loss: float,
    window: int = 5,
    use_fuel: bool = False,
    current_fuel: float = 0.0,
    cons_per_lap: float = 0.0,
    race_temp: float = 0.0,
) -> Optional[dict]:
    """Compare current race state vs chosen plan and recommend an adjustment.

    Returns a dict with:
      - status: "finished" | "last_stint" | "on_plan" | "pit_earlier" | "pit_later"
      - planned_pit_lap: int or None
      - recommended_pit_lap: int or None
      - next_compound: str (display name) or None
      - time_saving: float (positive = saves seconds vs staying on plan)

    Returns None if recommendation is not possible (no model, compound mismatch).

    The algorithm evaluates total remaining time (current tires until pit +
    pit_loss + next compound to end) for every lap in [planned±window],
    finds the minimum, and compares against the planned pit lap.
    A deviation >1 s triggers recommendation to pit earlier/later.
    """
    current_compound = canonical_compound(current_compound)

    if not models or not chosen_plan:
        return None

    rem_total = total_race_laps - current_lap
    if rem_total <= 0:
        return {"status": "finished", "planned_pit_lap": None, "next_compound": None, "time_saving": 0.0}

    # Locate which stint of the plan we are currently in
    cumulative = 0
    stint_idx = len(chosen_plan) - 1  # default: last stint
    for i, stint in enumerate(chosen_plan):
        cumulative += stint["laps"]
        if current_lap < cumulative:
            stint_idx = i
            break

    # Last planned stint — no more pits
    if stint_idx >= len(chosen_plan) - 1:
        return {
            "status": "last_stint",
            "planned_pit_lap": None,
            "next_compound": None,
            "time_saving": 0.0,
        }

    # Planned pit lap = end of current stint
    planned_pit_lap = sum(s["laps"] for s in chosen_plan[: stint_idx + 1])
    next_compound = canonical_compound(chosen_plan[stint_idx + 1]["compound"])

    if current_compound not in models or next_compound not in models:
        return None

    cur_coeffs = models[current_compound]
    nxt_coeffs = models[next_compound]

    def _eval_pit_at(pit_lap: int) -> Optional[float]:
        laps_before = pit_lap - current_lap
        laps_after = total_race_laps - pit_lap
        if laps_before < 1 or laps_after < 1:
            return None

        ages_b = np.arange(current_tire_age, current_tire_age + laps_before)
        ages_a = np.arange(0, laps_after)

        # Effective base for current compound
        if len(cur_coeffs) == 4:
            a_c, b_c, cf_c, dt_c = cur_coeffs
            a_c = a_c + dt_c * race_temp
        elif len(cur_coeffs) == 3:
            a_c, b_c, cf_c = cur_coeffs
        else:
            a_c, b_c = cur_coeffs[0], cur_coeffs[1]
            cf_c = 0.0

        # Effective base for next compound
        if len(nxt_coeffs) == 4:
            a_n, b_n, cf_n, dt_n = nxt_coeffs
            a_n = a_n + dt_n * race_temp
        elif len(nxt_coeffs) == 3:
            a_n, b_n, cf_n = nxt_coeffs
        else:
            a_n, b_n = nxt_coeffs[0], nxt_coeffs[1]
            cf_n = 0.0

        try:
            if use_fuel and cf_c != 0.0:
                fuel_seq_b = current_fuel - cons_per_lap * np.arange(0, laps_before)
                if (fuel_seq_b < 0).any():
                    return None
                t_before = float(np.sum(a_c + b_c * ages_b + cf_c * fuel_seq_b))
                fuel_at_pit = current_fuel - cons_per_lap * laps_before
            else:
                t_before = float(np.sum(a_c + b_c * ages_b))
                fuel_at_pit = current_fuel - cons_per_lap * laps_before

            if use_fuel and cf_n != 0.0:
                fuel_seq_a = fuel_at_pit - cons_per_lap * np.arange(0, laps_after)
                if (fuel_seq_a < 0).any():
                    return None
                t_after = float(np.sum(a_n + b_n * ages_a + cf_n * fuel_seq_a))
            else:
                t_after = float(np.sum(a_n + b_n * ages_a))
        except Exception:
            return None

        return t_before + pit_loss + t_after

    planned_time = _eval_pit_at(planned_pit_lap)
    if planned_time is None:
        return {
            "status": "on_plan",
            "planned_pit_lap": planned_pit_lap,
            "recommended_pit_lap": planned_pit_lap,
            "next_compound": display_compound(next_compound),
            "time_saving": 0.0,
        }

    best_pit_lap = planned_pit_lap
    best_time = planned_time

    lo = max(current_lap + 1, planned_pit_lap - window)
    hi = min(total_race_laps - 1, planned_pit_lap + window)
    for candidate in range(lo, hi + 1):
        if candidate == planned_pit_lap:
            continue
        t = _eval_pit_at(candidate)
        if t is not None and t < best_time:
            best_time = t
            best_pit_lap = candidate

    time_saving = planned_time - best_time  # positive = saves time
    delta = best_pit_lap - planned_pit_lap

    if abs(time_saving) < 1.0:
        status = "on_plan"
    elif delta < 0:
        status = "pit_earlier"
    else:
        status = "pit_later"

    return {
        "status": status,
        "planned_pit_lap": planned_pit_lap,
        "recommended_pit_lap": best_pit_lap,
        "next_compound": display_compound(next_compound),
        "time_saving": time_saving,
    }
