import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd


@dataclass
class Stint:
    stint_number: int
    start_lap: int
    end_lap: int
    compound: str
    total_laps: int
    avg_lap_time: float
    avg_track_temp: float
    avg_air_temp: float
    avg_fl_temp: float
    avg_fr_temp: float
    avg_rl_temp: float
    avg_rr_temp: float


SESSION_COL_MAP = {
    "lap": "currentLap",
    "lap_time_col": "lastLapTime",  # last completed lap time appears after crossing line
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
    df = pd.read_csv(csv_path)
    # Normalize timestamp
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Filter only rows that have lap info
    if SESSION_COL_MAP['lap'] in df.columns:
        df = df.sort_values('timestamp')
    return df


def detect_pit_events(df: pd.DataFrame) -> pd.DataFrame:
    """Annotate dataframe with pit_stop flag using multiple heuristics.

    Heuristics (any true -> pit_stop row):
    1. Tire age resets to 0 (classic out-lap) after previous > 0.
    2. Tire age decreases (reset) even if not exactly 0 (some exports start out-lap at 1).
    3. Compound changes and new tire_age <= 1.
    (Future: could integrate speed in pit lane / pit time if columns exist.)
    """
    if SESSION_COL_MAP['lap'] not in df.columns:
        df['pit_stop'] = False
        return df
    # Optional external logger column (string like 'IN PIT', 'PIT', etc.)
    pit_status_col = None
    for cand in ['pitstopStatus', 'pitStopStatus', 'pit_status']:
        if cand in df.columns:
            pit_status_col = cand
            break
    if SESSION_COL_MAP['tire_age'] not in df.columns:
        comp = df.get(SESSION_COL_MAP['compound'])
        base_flags = comp.ne(comp.shift(1)).fillna(False) if isinstance(comp, pd.Series) else pd.Series(False, index=df.index)
        if pit_status_col:
            ps = df[pit_status_col].astype(str).str.lower()
            status_flags = ps.str.contains('pit') | ps.str.contains('stop')
            df['pit_stop'] = (base_flags | status_flags).fillna(False)
        else:
            df['pit_stop'] = base_flags
        return df
    tire_age = pd.to_numeric(df[SESSION_COL_MAP['tire_age']], errors='coerce')
    lap = pd.to_numeric(df[SESSION_COL_MAP['lap']], errors='coerce')
    comp = df.get(SESSION_COL_MAP['compound'])
    if not isinstance(comp, pd.Series):
        comp = None
    age_prev = tire_age.shift(1)
    comp_prev = comp.shift(1) if comp is not None else None
    reset_zero = (tire_age == 0) & (age_prev > 0) & (lap > 0)
    age_drop = (tire_age < age_prev) & (age_prev >= 2) & (lap > 0)
    if comp is not None and comp_prev is not None:
        comp_str = comp.astype(str)
        comp_prev_str = comp_prev.astype(str)
        comp_change = (comp_str.ne(comp_prev_str) & (tire_age <= 1))
    else:
        comp_change = pd.Series(False, index=df.index)
    pit_flags = (reset_zero | age_drop | comp_change).fillna(False)
    if pit_status_col:
        ps = df[pit_status_col].astype(str).str.lower()
        status_flags = ps.str.contains('pit') | ps.str.contains('stop')
        pit_flags = (pit_flags | status_flags).fillna(False)
    df['pit_stop'] = pit_flags
    return df


def _parse_lap_time_to_seconds(v):
    """Acepta float en segundos o cadenas tipo 'm:ss.xxx' y devuelve segundos (float)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    m = re.match(r'^(?:(\d+):)?(\d+(?:\.\d+)?)$', s)
    if not m:
        return None
    mins = int(m.group(1) or 0)
    secs = float(m.group(2))
    return mins * 60 + secs


def build_lap_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per completed lap with key metrics.

    Pit stop flag is promoted to lap-level if any pit_stop row occurs within that lap
    (the lap where the out-lap begins gets pit_stop=True).
    """
    lap_col = SESSION_COL_MAP['lap']
    if lap_col not in df.columns:
        return pd.DataFrame()
    ordered = df.sort_values('timestamp')
    # Derive lap-level pit flag (any pit event within lap)
    if 'pit_stop' in ordered.columns:
        pit_by_lap = ordered.groupby(lap_col)['pit_stop'].any()
    else:
        pit_by_lap = pd.Series(False, index=ordered[lap_col].unique())
    # Keep last row per lap
    lap_last = ordered.groupby(lap_col).tail(1).copy()
    # Add lap-level pit flag (ensure boolean)
    lap_last['pit_stop'] = lap_last[lap_col].map(pit_by_lap).fillna(False)
    # Parse lap time
    if SESSION_COL_MAP['lap_time_col'] in lap_last.columns:
        lap_last['lap_time_s'] = lap_last[SESSION_COL_MAP['lap_time_col']].apply(_parse_lap_time_to_seconds)
    cols = [lap_col, 'lap_time_s', SESSION_COL_MAP['compound'], SESSION_COL_MAP['tire_age'],
            SESSION_COL_MAP['track_temp'], SESSION_COL_MAP['air_temp'], SESSION_COL_MAP['fl_temp'],
            SESSION_COL_MAP['fr_temp'], SESSION_COL_MAP['rl_temp'], SESSION_COL_MAP['rr_temp'], 'fuel', 'pit_stop']
    existing = [c for c in cols if c in lap_last.columns]
    return lap_last[existing].reset_index(drop=True)


def build_stints(lap_summary: pd.DataFrame) -> List[Stint]:
    stints: List[Stint] = []
    if lap_summary.empty:
        return stints
    current_compound = None
    stint_start_lap = None
    stint_number = 0
    for _, row in lap_summary.iterrows():
        compound = row.get(SESSION_COL_MAP['compound'])
        lap_val = row.get('currentLap')
        if lap_val is None:
            continue
        try:
            lap = int(lap_val)
        except (TypeError, ValueError):
            continue
        tire_age = row.get(SESSION_COL_MAP['tire_age'])
        is_pit = bool(row.get('pit_stop'))
        is_reset_age = (pd.notna(tire_age) and tire_age == 0)
        if current_compound is None:
            current_compound = compound
            stint_start_lap = lap
            stint_number = 1
        # If pit stop occurred (detected on the OUT lap) start new stint
        elif is_pit or (is_reset_age and stint_start_lap is not None and lap > stint_start_lap):
            # Close previous
            prev = lap_summary[(lap_summary['currentLap'] >= stint_start_lap) & (lap_summary['currentLap'] < lap)]
            if not prev.empty:
                stints.append(_aggregate_stint(prev, stint_number, current_compound))
            stint_number += 1
            current_compound = compound
            stint_start_lap = lap
    # Close final stint
    if stint_start_lap is not None:
        last_stint_rows = lap_summary[lap_summary['currentLap'] >= stint_start_lap]
        if not last_stint_rows.empty and current_compound is not None:
            stints.append(_aggregate_stint(last_stint_rows, stint_number, current_compound))
    return stints


def _aggregate_stint(stint_rows: pd.DataFrame, stint_number: int, compound: str) -> Stint:
    metrics = {
        'avg_lap_time': stint_rows['lap_time_s'].mean(skipna=True),
        'avg_track_temp': stint_rows.get(SESSION_COL_MAP['track_temp'], pd.Series(dtype=float)).mean(skipna=True),
        'avg_air_temp': stint_rows.get(SESSION_COL_MAP['air_temp'], pd.Series(dtype=float)).mean(skipna=True),
        'avg_fl_temp': stint_rows.get(SESSION_COL_MAP['fl_temp'], pd.Series(dtype=float)).mean(skipna=True),
        'avg_fr_temp': stint_rows.get(SESSION_COL_MAP['fr_temp'], pd.Series(dtype=float)).mean(skipna=True),
        'avg_rl_temp': stint_rows.get(SESSION_COL_MAP['rl_temp'], pd.Series(dtype=float)).mean(skipna=True),
        'avg_rr_temp': stint_rows.get(SESSION_COL_MAP['rr_temp'], pd.Series(dtype=float)).mean(skipna=True),
    }
    return Stint(
        stint_number=stint_number,
        start_lap=int(stint_rows['currentLap'].min()),
        end_lap=int(stint_rows['currentLap'].max()),
        compound=compound,
        total_laps=int(stint_rows['currentLap'].nunique()),
        **metrics,
    )


def fia_compliance_check(stints: List[Stint], weather_series: Optional[pd.Series]) -> dict:
    """Basic FIA-esque rule checks relevant to tyre usage.

    Simplified rules implemented:
    - If race remained Dry (no 'Rain' substring) -> at least two different dry compounds used.
    - No stint exceeds an arbitrary safety cap of 70% of race distance on one compound (heuristic to flag extreme usage).
    - At least one pit stop in races > 20 laps (heuristic).
    """
    result = {"used_two_compounds": True, "max_stint_ok": True, "pit_stop_required": True, "notes": []}
    if not stints:
        result['notes'].append('Sin stints detectados.')
        return result
    compounds = {s.compound for s in stints}
    total_laps = sum(s.total_laps for s in stints)
    weather_text = ' '.join(weather_series.dropna().unique()) if weather_series is not None else ''
    is_dry = 'Rain' not in weather_text and 'Wet' not in weather_text
    if is_dry and len(compounds) < 2 and total_laps >= 10:
        result['used_two_compounds'] = False
        result['notes'].append('Menos de dos compuestos usados en condiciones secas.')
    max_allowed = int(total_laps * 0.7)
    if any(s.total_laps > max_allowed for s in stints) and total_laps >= 15:
        result['max_stint_ok'] = False
        result['notes'].append('Un stint supera el 70% de la distancia total (bandera heurística).')
    if len(stints) < 2 and total_laps > 20:
        result['pit_stop_required'] = False
        result['notes'].append('Carrera larga con una sola parada / sin paradas.')
    return result


def load_all_sessions(root: Path) -> pd.DataFrame:
    csvs = list(root.glob('**/*.csv'))
    frames = []
    for p in csvs:
        try:
            df = load_session_csv(p)
            df['source_file'] = str(p.relative_to(root))
            frames.append(df)
        except Exception:  # noqa
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
