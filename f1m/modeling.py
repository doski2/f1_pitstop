from __future__ import annotations

from .common import canonical_compound
from .imports import (
    COL_AVG_WEAR,
    COL_PACE_MODE,
    COL_RAIN,
    COL_RUBBER,
    COL_SAFETY_CAR,
    MIN_RUBBER_STD,
    MIN_TEMP_STD,
    RAIN_TIME_MULTIPLIER,
    SAFETY_CAR_TIME_MULTIPLIER,
    WEAR_CLIFF,
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

    # Rubber detrending: remove global track-grip trend from lap times so that
    # b_age captures pure tire degradation, not the confounded rubber build-up.
    # Uses a global linear OLS fit (all compounds, all laps) then subtracts the
    # rubber effect evaluated at each lap, normalised to the session mean rubber.
    _rubber_col = COL_RUBBER
    rubber_available = (
        _rubber_col in practice_laps.columns
        and practice_laps[_rubber_col].notna().sum() >= 5
        and float(practice_laps[_rubber_col].std()) > MIN_RUBBER_STD
    )
    if rubber_available:
        _session_col = "session" if "session" in practice_laps.columns else None
        if _session_col is not None:
            # Per-session detrending: removes within-session track evolution only.
            # Global detrending across FP1/FP2/FP3 causes multicollinearity because
            # rubber also increases between sessions alongside fuel, temp, and setup changes.
            for _sess_id, _sess_mask in practice_laps.groupby(_session_col).groups.items():
                sess_rows = practice_laps.loc[_sess_mask]
                valid_s = sess_rows[[_rubber_col, "lap_time_s"]].notna().all(axis=1)
                valid_s = valid_s[valid_s].index
                if len(valid_s) < 3:
                    continue
                r_s = np.array(sess_rows.loc[valid_s, _rubber_col].values, dtype=np.float64)
                if float(r_s.std()) <= MIN_RUBBER_STD:
                    continue
                lt_s = sess_rows.loc[valid_s, "lap_time_s"].values.astype(float)
                A_r = np.column_stack([np.ones_like(r_s), r_s])  # type: ignore[call-overload]
                coef_r, *_ = np.linalg.lstsq(A_r, lt_s, rcond=None)  # type: ignore[call-overload]
                e_rubber = float(coef_r[1])
                rubber_ref = float(sess_rows[_rubber_col].mean())
                practice_laps.loc[_sess_mask, "lap_time_s"] = (
                    practice_laps.loc[_sess_mask, "lap_time_s"]
                    - e_rubber * (practice_laps.loc[_sess_mask, _rubber_col] - rubber_ref)
                )
        else:
            # Fallback: global detrending (single-session data — no session column)
            valid_mask = practice_laps[[_rubber_col, "lap_time_s"]].notna().all(axis=1)
            if valid_mask.sum() >= 5:
                r_vals = practice_laps.loc[valid_mask, _rubber_col].values.astype(float)
                lt_vals = practice_laps.loc[valid_mask, "lap_time_s"].values.astype(float)
                A_r = np.column_stack([np.ones_like(r_vals), r_vals])  # type: ignore[call-overload]
                coef_r, *_ = np.linalg.lstsq(A_r, lt_vals, rcond=None)  # type: ignore[call-overload]
                e_rubber = float(coef_r[1])
                rubber_ref = float(practice_laps[_rubber_col].mean())
                practice_laps["lap_time_s"] = (
                    practice_laps["lap_time_s"] - e_rubber * (practice_laps[_rubber_col] - rubber_ref)
                )
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
        if COL_PACE_MODE in filtered_grp.columns:
            # Keep laps from the dominant pace mode of this compound — filters out
            # isolated attack/warm-up outlier laps without discarding the entire stint.
            # If the dominant mode covers < 5 laps, fall back to excluding only the
            # two most aggressive modes (Attack, Aggressive) which create artificially
            # high wear/time variance that skews the degradation slope.
            mode_counts = filtered_grp[COL_PACE_MODE].value_counts()
            if not mode_counts.empty:
                dominant_mode = mode_counts.index[0]
                dominant_laps = filtered_grp[filtered_grp[COL_PACE_MODE] == dominant_mode]
                if len(dominant_laps) >= 5 and dominant_laps["tire_age"].nunique() >= 2:
                    filtered_grp = dominant_laps
                else:
                    # Fallback: exclude only Attack and Aggressive
                    filtered_grp = filtered_grp[
                        ~filtered_grp[COL_PACE_MODE].isin(["Attack", "Aggressive"])
                    ]

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

        def _lap_base(a: float, c_fuel: float = 0.0, d_temp: float = 0.0) -> float:
            """Predicted base lap time at mean conditions (first lap, lap age=0)."""
            base_fuel = float(dfc["fuel"].mean()) if has_fuel and "fuel" in dfc.columns else 0.0
            base_temp = float(dfc[_temp_col].mean()) if has_temp and _temp_col in dfc.columns else 0.0
            return a + c_fuel * base_fuel + d_temp * base_temp

        def _coef_valid(a: float, b_age: float, c_fuel: float = 0.0, d_temp: float = 0.0) -> bool:
            """Physical sanity: predicted base time realistic, coefficients in range."""
            if not (55.0 <= _lap_base(a, c_fuel, d_temp) <= 220.0):
                return False
            if not (-1.0 <= b_age <= 10.0):
                return False
            if abs(c_fuel) > 1.0:  # >1 s/kg is unrealistic (F1 is ~0.03-0.07)
                return False
            if abs(d_temp) > 3.0:  # >3 s/°C is unrealistic
                return False
            return True

        if has_fuel and has_temp:
            fuel = dfc["fuel"].values.astype(float)
            temp = dfc[_temp_col].values.astype(float)
            A = np.column_stack([np.ones_like(X_age), X_age, fuel, temp])  # type: ignore[call-overload]
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)  # type: ignore[call-overload]
            a, b_age, c_fuel, d_temp = map(float, coef)
            if _coef_valid(a, b_age, c_fuel, d_temp):
                models[comp] = (a, b_age, c_fuel, d_temp)
                continue
            # 4-param invalid → try 3-param (drop temp)
            has_temp = False

        if has_fuel and not has_temp:
            fuel = dfc["fuel"].values.astype(float)
            A = np.column_stack([np.ones_like(X_age), X_age, fuel])  # type: ignore[call-overload]
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)  # type: ignore[call-overload]
            a, b_age, c_fuel = map(float, coef)
            if _coef_valid(a, b_age, c_fuel):
                models[comp] = (a, b_age, c_fuel)
                continue
            # 3-param invalid → fall back to 2-param
        elif has_temp and not has_fuel:
            temp = dfc[_temp_col].values.astype(float)
            A = np.column_stack([np.ones_like(X_age), X_age, temp])  # type: ignore[call-overload]
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)  # type: ignore[call-overload]
            a, b_age, d_temp = map(float, coef)
            if _coef_valid(a, b_age, 0.0, d_temp):
                models[comp] = (a, b_age, 0.0, d_temp)  # c_fuel placeholder = 0.0
                continue
            # temp-only 3-param invalid → fall back to 2-param

        # 2-param fallback (always store something if data is available)
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

    # Wear-based prediction: fit linear model avg_wear ~ tire_age and find the
    # lap where predicted wear crosses the cliff threshold.
    # In F1 Manager, flDeg/rrDeg represent REMAINING life (1.0=new → 0.0=destroyed),
    # so b_w is NEGATIVE (decreasing). The cliff is 1.0 - WEAR_CLIFF/100.
    if COL_AVG_WEAR in subset.columns:
        wear_data = subset[["tire_age", COL_AVG_WEAR]].dropna()
        wear_data = wear_data[wear_data[COL_AVG_WEAR] > 0]
        if len(wear_data) >= 3 and wear_data["tire_age"].nunique() >= 2:
            _ages_w = np.array(wear_data["tire_age"].values, dtype=float)
            X_w = np.column_stack([np.ones(len(_ages_w)), _ages_w])
            y_w = wear_data[COL_AVG_WEAR].values.astype(float)
            coef_w, *_ = np.linalg.lstsq(X_w, y_w, rcond=None)  # type: ignore[call-overload]
            a_w, b_w = float(coef_w[0]), float(coef_w[1])
            # Determine scale: values > 1.5 are %-worn (0→100), else fraction remaining (0→1)
            if float(wear_data[COL_AVG_WEAR].max()) > 1.5:
                # %-worn scale: find when wear > WEAR_CLIFF
                if b_w > 0:
                    max_lap = int((WEAR_CLIFF - a_w) / b_w)
                    if 5 <= max_lap <= 60:
                        return max_lap
            else:
                # Fraction-remaining scale: find when remaining < (1 - WEAR_CLIFF/100)
                cliff_remaining = 1.0 - WEAR_CLIFF / 100.0
                if b_w < 0:
                    max_lap = int((cliff_remaining - a_w) / b_w)
                    if 5 <= max_lap <= 60:
                        return max_lap

    # Fallback: last observed tire_age + small buffer
    max_age = int(subset["tire_age"].max())
    return max_age + 2
