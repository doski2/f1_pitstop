from __future__ import annotations

from .common import canonical_compound
from .imports import (
    COL_RAIN,
    COL_SAFETY_CAR,
    MIN_TEMP_STD,
    RAIN_TIME_MULTIPLIER,
    SAFETY_CAR_TIME_MULTIPLIER,
    Dict,
    Tuple,
    Union,
    np,
    pd,
)


def fit_degradation_model(
    practice_laps: pd.DataFrame,
) -> Dict[str, Union[Tuple[float, float], Tuple[float, float, float], Tuple[float, float, float, float]]]:
    models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float], Tuple[float, float, float, float]]] = {}
    if practice_laps.empty:
        return models
    # Normalise all raw compound IDs/specs to canonical hardness categories so
    # that variants like "C3" and "C4" are merged into "Soft" for regression.
    practice_laps = practice_laps.copy()
    practice_laps["compound"] = practice_laps["compound"].apply(canonical_compound)
    fuel_available = (
        "fuel" in practice_laps.columns
        and practice_laps["fuel"].notna().sum() >= 5
        and practice_laps["fuel"].std() > 0.5
    )
    _temp_col = "trackTemp"
    temp_available = (
        _temp_col in practice_laps.columns
        and practice_laps[_temp_col].notna().sum() >= 5
        and float(practice_laps[_temp_col].std()) > MIN_TEMP_STD
    )
    for comp_raw, grp in practice_laps.groupby("compound"):
        comp = str(comp_raw)
        if grp["tire_age"].nunique() < 2 or len(grp) < 5:
            continue

        # Filter out laps with Safety Car, rain or any pit stop (inflated lap times)
        filtered_grp = grp.copy()
        if COL_SAFETY_CAR in grp.columns:
            filtered_grp = filtered_grp[~filtered_grp[COL_SAFETY_CAR].fillna(False)]
        if COL_RAIN in grp.columns:
            filtered_grp = filtered_grp[~filtered_grp[COL_RAIN].fillna(False)]
        if "pit_stop" in filtered_grp.columns:
            filtered_grp = filtered_grp[~filtered_grp["pit_stop"].fillna(False)]

        # If we don't have enough data after filtering, skip this compound
        if len(filtered_grp) < 5 or filtered_grp["tire_age"].nunique() < 2:
            continue

        cols = ["tire_age", "lap_time_s"]
        if fuel_available and "fuel" in filtered_grp.columns:
            cols.append("fuel")
        if temp_available and _temp_col in filtered_grp.columns:
            cols.append(_temp_col)
        dfc = filtered_grp[cols].dropna()
        if len(dfc) < 5:
            continue
        z = (dfc["lap_time_s"] - dfc["lap_time_s"].mean()) / (
            dfc["lap_time_s"].std(ddof=0) or 1
        )
        dfc = dfc[np.abs(z) < 3]
        if len(dfc) < 5:
            continue
        X_age = dfc["tire_age"].values.astype(float)
        y = dfc["lap_time_s"].values.astype(float)
        has_fuel = fuel_available and "fuel" in dfc.columns
        has_temp = temp_available and _temp_col in dfc.columns
        if has_fuel and has_temp:
            fuel = dfc["fuel"].values.astype(float)
            temp = dfc[_temp_col].values.astype(float)
            A = np.column_stack([np.ones_like(X_age), X_age, fuel, temp])  # type: ignore[call-overload]
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)  # type: ignore[call-overload]
            a, b_age, c_fuel, d_temp = map(float, coef)
            models[comp] = (a, b_age, c_fuel, d_temp)
        elif has_fuel:
            fuel = dfc["fuel"].values.astype(float)
            A = np.column_stack([np.ones_like(X_age), X_age, fuel])  # type: ignore[call-overload]
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)  # type: ignore[call-overload]
            a, b_age, c_fuel = map(float, coef)
            models[comp] = (a, b_age, c_fuel)
        elif has_temp:
            temp = dfc[_temp_col].values.astype(float)
            A = np.column_stack([np.ones_like(X_age), X_age, temp])  # type: ignore[call-overload]
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)  # type: ignore[call-overload]
            a, b_age, d_temp = map(float, coef)
            models[comp] = (a, b_age, 0.0, d_temp)  # c_fuel placeholder = 0.0
        else:
            A = np.column_stack([np.ones_like(X_age), X_age])  # type: ignore[call-overload]
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)  # type: ignore[call-overload]
            a, b_age = map(float, coef)
            models[comp] = (a, b_age)
    return models


def stint_time(intercept: float, slope: float, laps: int) -> float:
    if laps <= 0:
        return 0.0
    return laps * intercept + slope * (laps - 1) * laps / 2.0


def adjust_lap_time_for_conditions(
    base_lap_time: float, safety_car: bool = False, rain: bool = False
) -> float:
    """Adjust lap time based on Safety Car or rain conditions.

    Args:
        base_lap_time: Base lap time from degradation model
        safety_car: Whether Safety Car is deployed
        rain: Whether it's raining

    Returns:
        Adjusted lap time considering conditions
    """
    multiplier = 1.0

    if safety_car:
        multiplier *= SAFETY_CAR_TIME_MULTIPLIER
    if rain:
        multiplier *= RAIN_TIME_MULTIPLIER

    return base_lap_time * multiplier


def max_stint_length(practice_laps: pd.DataFrame, compound: str) -> int:
    # Normalise both the lookup key and the data column so "C3"/"C4" → "Soft"
    compound = canonical_compound(compound)
    canonical_col = practice_laps["compound"].apply(canonical_compound)
    subset = practice_laps[canonical_col == compound]
    if subset.empty:
        if compound.lower().startswith("soft"):
            return 18
        if compound.lower().startswith("medium"):
            return 28
        if compound.lower().startswith("hard"):
            return 40
        return 25
    max_age = int(subset["tire_age"].max())
    return max_age + 2
