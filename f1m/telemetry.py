"""f1m.telemetry

Utilidades de telemetría: lectura CSV, detección de pitstops, resumen por vuelta,
construcción de stints y chequeo básico de normativa FIA.

Este módulo no depende de Streamlit ni de librerías de visualización: puede usarse
como biblioteca desde CLI, notebooks o tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd


@dataclass
class Stint:
    """Estructura de un stint detectado en carrera/prácticas.

    Los promedios ignoran NaN. `total_laps` cuenta vueltas únicas del stint.
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
    """Carga un CSV de sesión con normalización mínima.

    - Convierte `timestamp` (si existe) a datetime.
    - Ordena por `timestamp` si existe `currentLap`.
    """

    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    if SESSION_COL_MAP["lap"] in df.columns and "timestamp" in df.columns:
        df = df.sort_values("timestamp")
    return df


def detect_pit_events(df: pd.DataFrame) -> pd.DataFrame:
    """Añade columna booleana `pit_stop` usando heurísticas.

    Heurísticas implementadas:
    - Reinicio de `tire_age` a 0 o caída pronunciada.
    - Cambio de compuesto con `tire_age` ≤ 1.
    - (si existe) flags en columnas tipo `pitstopStatus`.
    """

    if SESSION_COL_MAP["lap"] not in df.columns:
        df["pit_stop"] = False
        return df

    pit_status_col: Optional[str] = None
    for cand in ["pitstopStatus", "pitStopStatus", "pit_status"]:
        if cand in df.columns:
            pit_status_col = cand
            break

    # If there's no tire_age column, detect pit by compound change or explicit flags
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
    """Acepta float en segundos o cadenas tipo 'm:ss.xxx' y devuelve segundos.

    Devuelve None si no puede parsear.
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
    """Devuelve un DataFrame con una fila por vuelta completada.

    Columnas típicas: currentLap, lap_time_s, compound, tire_age, temperaturas (si existen),
    fuel (si existe) y `pit_stop` a nivel de vuelta.
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
    """Agrega métricas de un bloque contiguo de vueltas (`stint_rows`).

    Requiere que `stint_rows` pertenezca a un solo stint.
    """

    metrics = {
        "avg_lap_time": stint_rows["lap_time_s"].mean(skipna=True),
        "avg_track_temp": stint_rows.get(
            SESSION_COL_MAP["track_temp"], pd.Series(dtype=float)
        ).mean(skipna=True),
        "avg_air_temp": stint_rows.get(
            SESSION_COL_MAP["air_temp"], pd.Series(dtype=float)
        ).mean(skipna=True),
        "avg_fl_temp": stint_rows.get(
            SESSION_COL_MAP["fl_temp"], pd.Series(dtype=float)
        ).mean(skipna=True),
        "avg_fr_temp": stint_rows.get(
            SESSION_COL_MAP["fr_temp"], pd.Series(dtype=float)
        ).mean(skipna=True),
        "avg_rl_temp": stint_rows.get(
            SESSION_COL_MAP["rl_temp"], pd.Series(dtype=float)
        ).mean(skipna=True),
        "avg_rr_temp": stint_rows.get(
            SESSION_COL_MAP["rr_temp"], pd.Series(dtype=float)
        ).mean(skipna=True),
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
    """Construye la lista de stints a partir de `lap_summary`.

    Crea un nuevo stint ante un pit detectado o reinicio de `tire_age` (edad=0).
    """

    if lap_summary.empty:
        return []

    lap_col = SESSION_COL_MAP["lap"]
    stints: List[Stint] = []

    # Ensure lap_summary is ordered by lap
    ordered = lap_summary.sort_values(lap_col)

    # Identify changes that start a new stint
    change_mask = (
        ordered[SESSION_COL_MAP["compound"]]
        .astype(str)
        .ne(ordered[SESSION_COL_MAP["compound"]].shift(1).astype(str))
    )
    tire_age = ordered.get(SESSION_COL_MAP["tire_age"])
    if tire_age is not None:
        reset_age = (tire_age == 0) & (tire_age.shift(1) > 0)
        change_mask = change_mask | reset_age.fillna(False)

    # Also create a stint start where pit_stop is True
    if "pit_stop" in ordered.columns:
        change_mask = change_mask | ordered["pit_stop"].fillna(False)

    # Mark stint ids
    stint_ids = change_mask.cumsum().fillna(0).astype(int)

    for stint_number, (stint_id, rows) in enumerate(
        ordered.groupby(stint_ids), start=1
    ):
        if rows.empty:
            continue
        compound = (
            str(rows[SESSION_COL_MAP["compound"]].dropna().iloc[0])
            if SESSION_COL_MAP["compound"] in rows.columns
            else "unknown"
        )
        stints.append(_aggregate_stint(rows, stint_number, compound))

    return stints


def fia_compliance_check(
    stints: List[Stint], weather_series: Optional[pd.Series]
) -> dict:
    """Chequeo heurístico de cumplimiento FIA (simplificado):
    - Dos compuestos en seco si la carrera es “suficientemente larga”.
    - Longitud de stint razonable (70% de la distancia total, bandera heurística).
    - Presencia de al menos una parada en carreras largas.
    """

    result = {
        "used_two_compounds": True,
        "max_stint_ok": True,
        "pit_stop_required": True,
        "notes": [],
    }
    if not stints:
        result["notes"].append("Sin stints detectados.")
        return result

    compounds = {s.compound for s in stints}
    total_laps = sum(s.total_laps for s in stints)
    weather_text = (
        " ".join(weather_series.dropna().unique()) if weather_series is not None else ""
    )
    is_dry = "Rain" not in weather_text and "Wet" not in weather_text

    if is_dry and len(compounds) < 2 and total_laps >= 10:
        result["used_two_compounds"] = False
        result["notes"].append("Menos de dos compuestos usados en condiciones secas.")

    max_allowed = int(total_laps * 0.7)
    if any(s.total_laps > max_allowed for s in stints) and total_laps >= 15:
        result["max_stint_ok"] = False
        result["notes"].append(
            "Un stint supera el 70% de la distancia total (bandera heurística)."
        )

    if len(stints) < 2 and total_laps > 20:
        result["pit_stop_required"] = False
        result["notes"].append("Carrera larga con una sola parada / sin paradas.")

    return result
