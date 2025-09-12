"""Telemetry utilities for f1m.

Provides CSV loading, pit detection heuristics, lap summaries and stint building.
All docstrings use plain ASCII to avoid parser issues on Windows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd


@dataclass
class Stint:
    """Structure describing a detected stint.

    Averages ignore NaN. ``total_laps`` counts unique laps in the stint.
    """

    stint_number: int
    start_lap: int
    end_lap: int
    compound: str
    total_laps: int
    avg_lap_time: Optional[float]
    avg_track_temp: Optional[float]
    avg_air_temp: Optional[float]
    avg_fl_temp: Optional[float]
    avg_fr_temp: Optional[float]
    avg_rl_temp: Optional[float]
    avg_rr_temp: Optional[float]


SESSION_COL_MAP = {
    "lap": "currentLap",
    "lap_time_col": "lastLapTime",
    "current_lap_time_col": "currentLapTime",
    "compound": "compound",
    "tire_age": "tire_age",
    "air_temp": "airTemp",
    "track_temp": "trackTemp",
    "fl_temp": "flTemp",
    "fr_temp": "frTemp",
    "rl_temp": "rlTemp",
    "rr_temp": "rrTemp",
    "weather": "weather",
}


def load_session_csv(csv_path: Path) -> pd.DataFrame:
    """Load and lightly normalize a session CSV.

    - Convert ``timestamp`` to datetime if present.
    - Sort by ``timestamp`` when ``currentLap`` exists.
    """

    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    if SESSION_COL_MAP["lap"] in df.columns and "timestamp" in df.columns:
        df = df.sort_values("timestamp")
    return df


def detect_pit_events(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean column 'pit_stop' using heuristics.

    Heuristics:
    - tire_age reset to 0 or a large drop
    - compound change when tire_age <= 1
    - explicit flags in pit status columns if present
    """

    if SESSION_COL_MAP["lap"] not in df.columns:
        df["pit_stop"] = False
        return df

    pit_status_col: Optional[str] = None
    for cand in ["pitstopStatus", "pitStopStatus", "pit_status"]:
        if cand in df.columns:
            pit_status_col = cand
            break

    if SESSION_COL_MAP["tire_age"] not in df.columns:
        comp = df.get(SESSION_COL_MAP["compound"])
        if isinstance(comp, pd.Series):
            base_flags = comp.ne(comp.shift(1)).fillna(False)
        else:
            base_flags = pd.Series(False, index=df.index)

        if pit_status_col:
            ps = df[pit_status_col].astype(str).str.lower()
            status_flags = ps.str.contains("pit") | ps.str.contains("stop")
            df["pit_stop"] = (base_flags | status_flags).fillna(False)
        else:
            df["pit_stop"] = base_flags
        return df

    tire_age = pd.to_numeric(df[SESSION_COL_MAP["tire_age"]], errors="coerce")
    lap = pd.to_numeric(df[SESSION_COL_MAP["lap"]], errors="coerce")
    comp = df.get(SESSION_COL_MAP["compound"])
    comp_prev = comp.shift(1) if isinstance(comp, pd.Series) else None
    age_prev = tire_age.shift(1)

    reset_zero = (tire_age == 0) & (age_prev > 0) & (lap > 0)
    age_drop = (tire_age < age_prev) & (age_prev >= 2) & (lap > 0)

    if isinstance(comp, pd.Series) and isinstance(comp_prev, pd.Series):
        comp_change = comp.astype(str).ne(comp_prev.astype(str)) & (tire_age <= 1)
    else:
        comp_change = pd.Series(False, index=df.index)

    pit_flags = (reset_zero | age_drop | comp_change).fillna(False)

    if pit_status_col:
        ps = df[pit_status_col].astype(str).str.lower()
        status_flags = ps.str.contains("pit") | ps.str.contains("stop")
        pit_flags = (pit_flags | status_flags).fillna(False)

    df["pit_stop"] = pit_flags
    return df


def _parse_lap_time_to_seconds(v) -> Optional[float]:
    """Accept floats (seconds) or strings like 'm:ss.xxx' and return seconds.

    Returns None when unparsable.
    """

    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    m = re.match(r"^(?:(\d+):)?(\d+(?:\.\d+)?)$", s)
    if not m:
        return None
    mins = int(m.group(1) or 0)
    secs = float(m.group(2))
    return mins * 60 + secs


def build_lap_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return one-row-per-lap summary with lap_time_s, compound, tire_age, temps, fuel, pit_stop.
    """

    lap_col = SESSION_COL_MAP["lap"]
    if lap_col not in df.columns:
        return pd.DataFrame()

    ordered = df.sort_values("timestamp") if "timestamp" in df.columns else df

    if "pit_stop" in ordered.columns:
        pit_by_lap = ordered.groupby(lap_col)["pit_stop"].any()
    else:
        pit_by_lap = pd.Series(False, index=ordered[lap_col].unique())

    lap_last = ordered.groupby(lap_col).tail(1).copy()
    lap_last["pit_stop"] = lap_last[lap_col].map(pit_by_lap).fillna(False)

    if SESSION_COL_MAP["lap_time_col"] in lap_last.columns:
        lap_last["lap_time_s"] = lap_last[SESSION_COL_MAP["lap_time_col"]].apply(
            _parse_lap_time_to_seconds
        )

    cols = [
        lap_col,
        "lap_time_s",
        SESSION_COL_MAP["compound"],
        SESSION_COL_MAP["tire_age"],
        SESSION_COL_MAP["track_temp"],
        SESSION_COL_MAP["air_temp"],
        SESSION_COL_MAP["fl_temp"],
        SESSION_COL_MAP["fr_temp"],
        SESSION_COL_MAP["rl_temp"],
        SESSION_COL_MAP["rr_temp"],
        "fuel",
        "pit_stop",
    ]

    existing = [c for c in cols if c in lap_last.columns]
    return lap_last[existing].reset_index(drop=True)


def _aggregate_stint(
    stint_rows: pd.DataFrame, stint_number: int, compound: str
) -> Stint:
    """Aggregate metrics for a contiguous block of laps belonging to a single stint."""

    metrics = {
        "avg_lap_time": stint_rows["lap_time_s"].mean(skipna=True),
        "avg_track_temp": stint_rows.get(SESSION_COL_MAP["track_temp"], pd.Series(dtype=float)).mean(skipna=True),
        "avg_air_temp": stint_rows.get(SESSION_COL_MAP["air_temp"], pd.Series(dtype=float)).mean(skipna=True),
        "avg_fl_temp": stint_rows.get(SESSION_COL_MAP["fl_temp"], pd.Series(dtype=float)).mean(skipna=True),
        "avg_fr_temp": stint_rows.get(SESSION_COL_MAP["fr_temp"], pd.Series(dtype=float)).mean(skipna=True),
        "avg_rl_temp": stint_rows.get(SESSION_COL_MAP["rl_temp"], pd.Series(dtype=float)).mean(skipna=True),
        "avg_rr_temp": stint_rows.get(SESSION_COL_MAP["rr_temp"], pd.Series(dtype=float)).mean(skipna=True),
    }

    return Stint(
        stint_number=stint_number,
        start_lap=int(stint_rows[SESSION_COL_MAP["lap"]].min()),
        end_lap=int(stint_rows[SESSION_COL_MAP["lap"]].max()),
        compound=compound,
        total_laps=int(stint_rows[SESSION_COL_MAP["lap"]].nunique()),
        **metrics,
    )


def build_stints(lap_summary: pd.DataFrame) -> List[Stint]:
    """Build stints list from lap summary.

    Starts a new stint on pit_stop True or when tire_age resets to 0.
    """

    if lap_summary.empty:
        return []

    lap_col = SESSION_COL_MAP["lap"]
    stints: List[Stint] = []

    ordered = lap_summary.sort_values(lap_col)

    change_mask = ordered.get(SESSION_COL_MAP["compound"], pd.Series(dtype=str)).astype(str).ne(
        ordered.get(SESSION_COL_MAP["compound"], pd.Series(dtype=str)).shift(1).astype(str)
    )
    tire_age = ordered.get(SESSION_COL_MAP["tire_age"])
    if tire_age is not None:
        reset_age = (tire_age == 0) & (tire_age.shift(1) > 0)
        change_mask = change_mask | reset_age.fillna(False)

    if "pit_stop" in ordered.columns:
        change_mask = change_mask | ordered["pit_stop"].fillna(False)

    stint_ids = change_mask.cumsum().fillna(0).astype(int)

    for stint_number, (_, rows) in enumerate(ordered.groupby(stint_ids), start=1):
        if rows.empty:
            continue
        compound = str(rows.get(SESSION_COL_MAP["compound"], pd.Series(dtype=str)).dropna().iloc[0]) if SESSION_COL_MAP["compound"] in rows.columns else "unknown"
        stints.append(_aggregate_stint(rows, stint_number, compound))

    return stints


def fia_compliance_check(stints: List[Stint], weather_series: Optional[pd.Series]) -> dict:
    """Simplified FIA compliance heuristics.

    - checks compound diversity in dry conditions
    - flags excessively long stints
    - warns when no pit stops in long races
    """

    result = {"used_two_compounds": True, "max_stint_ok": True, "pit_stop_required": True, "notes": []}
    if not stints:
        result["notes"].append("No stints detected.")
        return result

    compounds = {s.compound for s in stints}
    total_laps = sum(s.total_laps for s in stints)
    weather_text = " ".join(weather_series.dropna().unique()) if weather_series is not None else ""
    is_dry = "Rain" not in weather_text and "Wet" not in weather_text

    if is_dry and len(compounds) < 2 and total_laps >= 10:
        result["used_two_compounds"] = False
        result["notes"].append("Fewer than two compounds used in dry conditions.")

    max_allowed = int(total_laps * 0.7)
    if any(s.total_laps > max_allowed for s in stints) and total_laps >= 15:
        result["max_stint_ok"] = False
        result["notes"].append("A stint exceeds 70% of distance (heuristic).")

    if len(stints) < 2 and total_laps > 20:
        result["pit_stop_required"] = False
        result["notes"].append("Long race with a single or no stops detected.")

    return result
