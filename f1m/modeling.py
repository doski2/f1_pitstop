from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Union

import numpy as np
import pandas as pd

from .telemetry import build_lap_summary, load_session_csv

PRACTICE_SESSION_NAMES = {"Practice 1", "Practice 2", "Practice 3", "Practice", "FP1", "FP2", "FP3"}


def collect_practice_data(data_root: Path, track: str, driver: str) -> pd.DataFrame:
    track_dir = data_root / track
    frames = []
    if not track_dir.exists():
        return pd.DataFrame()
    for session_dir in track_dir.iterdir():
        if not session_dir.is_dir():
            continue
        if session_dir.name not in PRACTICE_SESSION_NAMES and not session_dir.name.startswith(
            "Practice"
        ):
            continue
        for d in session_dir.rglob(driver):
            if d.is_dir():
                for csv in d.glob("*.csv"):
                    try:
                        df = load_session_csv(csv)
                        lap_sum = build_lap_summary(df)
                        lap_sum["session"] = session_dir.name
                        frames.append(lap_sum)
                    except Exception:
                        continue
    if frames:
        out = pd.concat(frames, ignore_index=True)
        out = out[(out["lap_time_s"].notna()) & (out["lap_time_s"] > 0)]
        return out
    return pd.DataFrame()


def fit_degradation_model(
    practice_laps: pd.DataFrame,
) -> Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]]:
    models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]] = {}
    if practice_laps.empty:
        return models
    fuel_available = (
        "fuel" in practice_laps.columns
        and practice_laps["fuel"].notna().sum() >= 5
        and practice_laps["fuel"].std() > 0.5
    )
    for comp_raw, grp in practice_laps.groupby("compound"):
        comp = str(comp_raw)
        if grp["tire_age"].nunique() < 2 or len(grp) < 5:
            continue
        cols = ["tire_age", "lap_time_s"] + (
            ["fuel"] if fuel_available and "fuel" in grp.columns else []
        )
        dfc = grp[cols].dropna()
        if len(dfc) < 5:
            continue
        z = (dfc["lap_time_s"] - dfc["lap_time_s"].mean()) / (dfc["lap_time_s"].std(ddof=0) or 1)
        dfc = dfc[np.abs(z) < 3]
        if len(dfc) < 5:
            continue
        X_age = dfc["tire_age"].values.astype(float)
        y = dfc["lap_time_s"].values.astype(float)
        if fuel_available and "fuel" in dfc.columns:
            fuel = dfc["fuel"].values.astype(float)
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
    if laps <= 0:
        return 0.0
    return laps * intercept + slope * (laps - 1) * laps / 2.0


def max_stint_length(practice_laps: pd.DataFrame, compound: str) -> int:
    subset = practice_laps[practice_laps["compound"] == compound]
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
