"""Cached data-loading, model-management, and sidebar-support functions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Union

import pandas as pd
import streamlit as st
from _imports import (
    build_lap_summary,
    build_stints,
    collect_practice_data,
    detect_pit_events,
    enumerate_plans,
    fia_compliance_check,
    fit_degradation_model,
    load_session_csv,
)


@st.cache_data(show_spinner=False)
def list_tracks(data_root: Path) -> list[str]:
    return sorted([p.name for p in data_root.iterdir() if p.is_dir()])


@st.cache_data(show_spinner=False)
def list_sessions_for(track_dir: Path) -> list[str]:
    return sorted([p.name for p in track_dir.iterdir() if p.is_dir()])


@st.cache_data(show_spinner=False)
def list_drivers_for(session_dir: Path) -> list[str]:
    drivers: set[str] = set()
    for d in session_dir.rglob("*"):
        if d.is_dir() and any(f.suffix == ".csv" for f in d.glob("*.csv")):
            drivers.add(d.name)
    return sorted(drivers)


def autorefresh_guarded(enabled: bool, interval_ms: int = 15000) -> None:
    if enabled and not st.session_state["auto_guard"]:
        st.session_state["auto_guard"] = True
    if enabled:
        _autoref = getattr(st, "autorefresh", None)
        if callable(_autoref):
            _autoref(interval=interval_ms, key="auto_rfr")

def load_precomputed_model(models_root: Path, track: str, driver: str):
    path = models_root / track / f"{driver}_model.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("models", {})
            models: dict[
                str, Union[Tuple[float, float], Tuple[float, float, float]]
            ] = {}
            for comp, coeffs in raw.items():
                if isinstance(coeffs, list):
                    if len(coeffs) == 2:
                        models[comp] = (float(coeffs[0]), float(coeffs[1]))
                    elif len(coeffs) == 3:
                        models[comp] = (
                            float(coeffs[0]),
                            float(coeffs[1]),
                            float(coeffs[2]),
                        )
            return models, data.get("metadata", {})
        except (
            json.JSONDecodeError,
            FileNotFoundError,
            KeyError,
            ValueError,
            IOError,
        ) as e:
            st.warning(f"Error cargando modelo precomputado: {type(e).__name__}: {e}")
    return {}, {}


@st.cache_data(show_spinner=True)
def load_practice_data(data_root: Path, track: str, driver: str) -> pd.DataFrame:
    """Carga datos de práctica con caché inteligente.

    La caché se invalida automáticamente cuando cambian los archivos de datos.
    """
    return collect_practice_data(data_root, track, driver)


@st.cache_data(show_spinner=True)
def fit_degradation_models(practice_data: pd.DataFrame):
    """Ajusta modelos de degradación con caché para evitar recálculos costosos."""
    return fit_degradation_model(practice_data)


@st.cache_data(show_spinner=False)
def generate_race_plans(
    race_laps: int,
    compounds: list,
    models: dict,
    practice_data: pd.DataFrame,
    pit_loss: float,
    max_stops: int = 2,
    min_stint: int = 5,
    require_two_compounds: bool = True,
    use_fuel: bool = False,
    start_fuel: float = 0.0,
    cons_per_lap: float = 0.0,
):
    """Genera planes de carrera con caché para evitar recálculos costosos."""
    return enumerate_plans(
        race_laps,
        compounds,
        models,
        practice_data,
        pit_loss,
        max_stops=max_stops,
        min_stint=min_stint,
        require_two_compounds=require_two_compounds,
        use_fuel=use_fuel,
        start_fuel=start_fuel,
        cons_per_lap=cons_per_lap,
    )


@st.cache_data(show_spinner=True)
def load_and_process(path: Path, mtime: float):
    """Carga y procesa un archivo de telemetría vía adapter F1 Manager 2024.
    mtime se incluye para invalidar cache cuando el archivo cambia.
    """
    df = load_session_csv(path)
    df = detect_pit_events(df)
    lap_summary = build_lap_summary(df)
    stints = build_stints(lap_summary)
    compliance = fia_compliance_check(stints, df.get("weather"))
    return df, lap_summary, stints, compliance


def save_model_json(
    models_root: Path,
    track: str,
    driver: str,
    models: dict,
    sessions_used: list,
    fuel_used: bool,
    app_version: str,
) -> None:
    models_root.mkdir(parents=True, exist_ok=True)
    out_dir = models_root / track
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "track": track,
            "driver": driver,
            "sessions_included": sessions_used,
            "fuel_used": fuel_used,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "app_version": app_version,
            "model_version": 1,
        },
        "models": {k: list(v) for k, v in models.items()},
    }
    out_path = out_dir / f"{driver}_model.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    st.success(f"Modelo guardado en {out_path}")
