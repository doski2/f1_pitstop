from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from strategy import load_session_csv, build_lap_summary


PRACTICE_SESSION_NAMES = {"Practice 1", "Practice 2", "Practice 3", "Practice", "FP1", "FP2", "FP3"}


def collect_practice_data(data_root: Path, track: str, driver: str) -> pd.DataFrame:
    """Aggregate lap summaries from all practice sessions for given track & driver."""
    track_dir = data_root / track
    frames = []
    if not track_dir.exists():
        return pd.DataFrame()
    for session_dir in track_dir.iterdir():
        if not session_dir.is_dir():
            continue
        if session_dir.name not in PRACTICE_SESSION_NAMES and not session_dir.name.startswith('Practice'):
            continue
        # Search within driver subdirs
        for d in session_dir.rglob(driver):
            if d.is_dir():
                for csv in d.glob('*.csv'):
                    try:
                        df = load_session_csv(csv)
                        lap_sum = build_lap_summary(df)
                        lap_sum['session'] = session_dir.name
                        frames.append(lap_sum)
                    except Exception:  # noqa
                        continue
    if frames:
        out = pd.concat(frames, ignore_index=True)
        # Clean lap_time_s (drop None / zeros)
        out = out[(out['lap_time_s'].notna()) & (out['lap_time_s'] > 0)]
        return out
    return pd.DataFrame()


def fit_degradation_model(practice_laps: pd.DataFrame) -> Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]]:
    models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]] = {}
    if practice_laps.empty:
        return models
    fuel_available = 'fuel' in practice_laps.columns and practice_laps['fuel'].notna().sum() >= 5 and practice_laps['fuel'].std() > 0.5
    for comp_raw, grp in practice_laps.groupby('compound'):
        comp = str(comp_raw)
        if grp['tire_age'].nunique() < 2 or len(grp) < 5:
            continue
        cols = ['tire_age', 'lap_time_s'] + (['fuel'] if fuel_available and 'fuel' in grp.columns else [])
        dfc = grp[cols].dropna()
        if len(dfc) < 5:
            continue
        z = (dfc['lap_time_s'] - dfc['lap_time_s'].mean()) / (dfc['lap_time_s'].std(ddof=0) or 1)
        dfc = dfc[np.abs(z) < 3]
        if len(dfc) < 5:
            continue
        X_age = dfc['tire_age'].values.astype(float)
        y = dfc['lap_time_s'].values.astype(float)
        if fuel_available and 'fuel' in dfc.columns:
            fuel = dfc['fuel'].values.astype(float)
            A = np.column_stack([np.ones_like(X_age), X_age, fuel])
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)
            a, b_age, c_fuel = map(float, coef)
            models[comp] = (a, b_age, c_fuel)
        else:
            A = np.column_stack([np.ones_like(X_age), X_age])
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)
            a, b_age = map(float, coef)
            models[comp] = (a, b_age)
    return models


def stint_time(intercept: float, slope: float, laps: int) -> float:
    """Closed form sum of arithmetic progression for linear degradation starting age 0.
    lap i time = intercept + slope * i  (i starting at 0) => total = laps*intercept + slope * (laps-1)*laps/2
    """
    if laps <= 0:
        return 0.0
    return laps * intercept + slope * (laps - 1) * laps / 2.0


def max_stint_length(practice_laps: pd.DataFrame, compound: str) -> int:
    """Heuristic maximum stint length for compound."""
    subset = practice_laps[practice_laps['compound'] == compound]
    if subset.empty:
        # Fallback typical limits
        if compound.lower().startswith('soft'):
            return 18
        if compound.lower().startswith('medium'):
            return 28
        if compound.lower().startswith('hard'):
            return 40
        return 25
    max_age = int(subset['tire_age'].max())
    # Add small buffer
    return max_age + 2


def enumerate_plans(race_laps: int, compounds: List[str], models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]],
                    practice_laps: pd.DataFrame, pit_loss: float, max_stops: int = 2, min_stint: int = 5,
                    require_two_compounds: bool = True, top_k: int = 3,
                    use_fuel: bool = False, start_fuel: float = 0.0, cons_per_lap: float = 0.0) -> List[dict]:
    """Brute force enumeration of strategies up to max_stops (so max_stops+1 stints)."""
    best: List[dict] = []

    # Precompute max length per compound
    max_len = {c: max_stint_length(practice_laps, c) for c in compounds}

    def add_plan(seq: List[Tuple[str, int]]):
        if sum(l for _, l in seq) != race_laps:
            return
        if require_two_compounds and len({c for c, _ in seq}) < 2 and race_laps > 15:
            return
        total = 0.0
        details = []
        feasible = True
        fuel_cursor = start_fuel
        for comp, l in seq:
            if comp not in models:
                feasible = False
                break
            coeffs = models[comp]
            if use_fuel and len(coeffs) == 3:
                a, b_age, c_fuel = coeffs
                ages = np.arange(0, l)
                fuel_series = fuel_cursor - cons_per_lap * ages
                stint_time_val = float(np.sum(a + b_age * ages + c_fuel * fuel_series))
                fuel_cursor -= cons_per_lap * l
            else:
                a, b_age = coeffs[0], coeffs[1]
                stint_time_val = stint_time(a, b_age, l)
            total += stint_time_val
            details.append({'compound': comp, 'laps': l, 'pred_time': stint_time_val})
        if not feasible:
            return
        total += pit_loss * (len(seq) - 1)
        best.append({'stints': details, 'total_time': total, 'stops': len(seq) - 1})

    def recurse(rem_laps: int, current: List[Tuple[str, int]], depth: int):
        if rem_laps == 0:
            add_plan(current)
            return
        if depth > max_stops:  # depth counts index; stops = len(stints)-1
            # If we already have more stints than allowed return
            return
        for comp in compounds:
            max_l = min(max_len.get(comp, rem_laps), rem_laps)
            for l in range(min_stint, max_l + 1):
                # Ensure final stint can be at least min_stint unless rem_laps-l ==0
                if rem_laps - l != 0 and rem_laps - l < min_stint:
                    continue
                recurse(rem_laps - l, current + [(comp, l)], depth + 1)

    recurse(race_laps, [], 0)
    best.sort(key=lambda x: x['total_time'])
    return best[:top_k]


def live_pit_recommendation(current_lap: int, total_race_laps: int, current_compound: str,
                             current_tire_age: int, models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]],
                             practice_laps: pd.DataFrame, pit_loss: float,
                             window: int = 12,
                             use_fuel: bool = False,
                             current_fuel: float = 0.0,
                             cons_per_lap: float = 0.0) -> Optional[dict]:
    """Evaluate candidate pit laps within window returning minimal projected total time to finish.
    Simple model: cost = remaining current compound laps + (pit_loss) + optimal final compound constant pace using best compound.
    """
    if current_compound not in models or not models:
        return None
    rem_laps = total_race_laps - current_lap
    if rem_laps <= 0:
        return None
    # Determine best alternative compound (could be same compound if rules allow)
    best_comp_alt = None
    best_single_lap = None
    for comp, coeffs in models.items():
        a = coeffs[0]
        if best_single_lap is None or a < best_single_lap:
            best_single_lap = a
            best_comp_alt = comp
    cur_coeffs = models[current_compound]
    if use_fuel and len(cur_coeffs) == 3:
        a_cur, b_cur, c_cur = cur_coeffs
    else:
        a_cur, b_cur = cur_coeffs[0], cur_coeffs[1]
        c_cur = None
    evaluations = []
    for pit_in in range(1, min(window, rem_laps) + 1):
        ages = np.arange(current_tire_age, current_tire_age + pit_in)
        if use_fuel and c_cur is not None:
            fuel_seg = current_fuel - cons_per_lap * np.arange(0, pit_in)
            time_current = float(np.sum(a_cur + b_cur * ages + c_cur * fuel_seg))
            fuel_after = current_fuel - cons_per_lap * pit_in
        else:
            time_current = float(np.sum(a_cur + b_cur * ages))
            fuel_after = current_fuel - cons_per_lap * pit_in
        laps_after = rem_laps - pit_in
        if laps_after < 0:
            continue
        if best_comp_alt is None:
            return None
        new_coeffs = models[best_comp_alt]
        if use_fuel and len(new_coeffs) == 3:
            a_new, b_new, c_new = new_coeffs
            new_ages = np.arange(0, laps_after)
            fuel_new = fuel_after - cons_per_lap * new_ages
            time_new = float(np.sum(a_new + b_new * new_ages + c_new * fuel_new))
        else:
            a_new, b_new = new_coeffs[0], new_coeffs[1]
            time_new = stint_time(a_new, b_new, laps_after)
        total = time_current + pit_loss + time_new
        evaluations.append({'pit_on_lap': current_lap + pit_in, 'continue_laps': pit_in, 'new_compound': best_comp_alt,
                            'projected_total_remaining': total})
    if not evaluations:
        return None
    return min(evaluations, key=lambda x: x['projected_total_remaining'])
