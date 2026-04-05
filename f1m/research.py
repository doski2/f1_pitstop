"""f1m/research.py

Recopilación incremental de datos de comportamiento de neumáticos.

Para cada sesión guardada, extrae métricas por compuesto (degradación de
tiempo, desgaste físico, modo dominante, R², etc.) y las acumula en:

  research/tire_behavior.json
    └── por circuito / piloto / compuesto / sesión

El archivo se actualiza de forma incremental: las nuevas sesiones se añaden
y las existentes se sobreescriben con los datos más recientes del mismo
(track, driver, compound, session_type).

Uso:
    from f1m.research import save_tire_research
    save_tire_research(research_root, track, driver, combined_laps, models)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, Tuple, Union

import numpy as np
import pandas as pd

from .common import canonical_compound
from .constants import (
    MIN_WEAR_RATE_PER_LAP,
    PACE_WEAR_SCALE,
    WEAR_CLIFF,
)
from .telemetry import COL_AVG_WEAR

# Tolerancias físicas: igual que las de fit_degradation_model
_B_AGE_RANGE = (-1.0, 10.0)
_B_W_RANGE = (-0.05, 0.0)  # fracción restante/vuelta (negativo)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return 0.0 if ss_tot == 0 else round(1.0 - ss_res / ss_tot, 4)


def _fit_wear_slope(ages: np.ndarray, wear: np.ndarray) -> Tuple[float, float, float]:
    """OLS wear ~ age. Devuelve (a_w, b_w, r2)."""
    X = np.column_stack([np.ones_like(ages), ages])
    coef, *_ = np.linalg.lstsq(X, wear, rcond=None)
    a_w, b_w = float(coef[0]), float(coef[1])
    pred = a_w + b_w * ages
    return a_w, b_w, _r2(wear, pred)


def _fit_time_slope(ages: np.ndarray, times: np.ndarray) -> Tuple[float, float, float]:
    """OLS lap_time ~ age. Devuelve (a_t, b_age, r2)."""
    X = np.column_stack([np.ones_like(ages), ages])
    coef, *_ = np.linalg.lstsq(X, times, rcond=None)
    a_t, b_age = float(coef[0]), float(coef[1])
    pred = a_t + b_age * ages
    return a_t, b_age, _r2(times, pred)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def save_tire_research(
    research_root: Path,
    track: str,
    driver: str,
    combined_laps: pd.DataFrame,
    models: Dict[str, Union[Tuple, list]],
) -> None:
    """Extrae métricas de neumáticos y las acumula en research/tire_behavior.json.

    Se llama justo después de save_model_json. Si el archivo ya existe, las
    entradas nuevas se añaden y las existentes se actualizan.
    """
    research_root.mkdir(parents=True, exist_ok=True)
    out_path = research_root / "tire_behavior.json"

    # Carga el archivo existente o comienza uno nuevo
    if out_path.exists():
        try:
            db: dict = json.loads(out_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            db = {}
    else:
        db = {}

    today = date.today().isoformat()
    laps = combined_laps.copy()
    laps["compound"] = laps["compound"].apply(canonical_compound)

    # Detectar columna de sesión
    session_col = "session" if "session" in laps.columns else None

    for comp_raw, grp in laps.groupby("compound"):
        comp = str(comp_raw)

        # Determinar el paceMode dominante global del compuesto
        dominant_mode = "Unknown"
        scale = 1.0
        if "paceMode" in grp.columns:
            mc = grp["paceMode"].value_counts()
            if not mc.empty:
                dominant_mode = str(mc.index[0])
                scale = PACE_WEAR_SCALE.get(dominant_mode, 1.0)

        # Desgaste físico (avg_wear)
        b_w_entry: dict = {}
        wear_col = COL_AVG_WEAR if COL_AVG_WEAR in grp.columns else None
        if wear_col:
            wd = grp[["tire_age", wear_col]].dropna()
            wd = wd[wd[wear_col] > 0]
            if len(wd) >= 3 and wd["tire_age"].nunique() >= 2:
                ages_w = np.array(wd["tire_age"].values, dtype=float)
                wear_v = np.array(wd[wear_col].values, dtype=float)
                a_w, b_w, r2_w = _fit_wear_slope(ages_w, wear_v)
                b_w_scaled = b_w * scale
                # Estimar max_stint con b_w escalado
                max_stint_est: int | None = None
                if wear_v.max() > 1.5:  # escala %-worn
                    if b_w_scaled > MIN_WEAR_RATE_PER_LAP:
                        ms = int((WEAR_CLIFF - a_w) / b_w_scaled)
                        max_stint_est = ms if 5 <= ms <= 60 else None
                else:  # fracción restante
                    cliff = 1.0 - WEAR_CLIFF / 100.0
                    if b_w_scaled < -MIN_WEAR_RATE_PER_LAP:
                        ms = int((cliff - a_w) / b_w_scaled)
                        max_stint_est = ms if 5 <= ms <= 60 else None
                b_w_entry = {
                    "a_w": round(a_w, 5),
                    "b_w_measured": round(b_w, 6),
                    "b_w_race_equiv": round(b_w_scaled, 6),
                    "r2_wear": r2_w,
                    "max_stint_est": max_stint_est,
                    "n_wear_laps": int(len(wd)),
                }

        # Degradación de tiempo (por sesión y global)
        time_entries: dict = {}
        sessions_iter = (
            grp.groupby(session_col).groups.items()
            if session_col
            else [("all", grp.index)]
        )
        for sess_id, idx in sessions_iter:
            sg = grp.loc[idx] if session_col else grp
            td = sg[["tire_age", "lap_time_s"]].dropna()
            if len(td) < 3 or td["tire_age"].nunique() < 2:
                continue
            # Filtrar outliers ±3σ
            z = (td["lap_time_s"] - td["lap_time_s"].mean()) / (
                td["lap_time_s"].std(ddof=0) or 1
            )
            td = td[np.abs(z.values) < 3]
            if len(td) < 3:
                continue
            ages_t = np.array(td["tire_age"].values, dtype=float)
            times_t = np.array(td["lap_time_s"].values, dtype=float)
            a_t, b_age, r2_t = _fit_time_slope(ages_t, times_t)
            # Escalar b_age al equivalente de carrera
            b_age_race = (
                b_age * scale if b_age > 0 else b_age
            )  # solo escala degradación, no ganancia
            time_entries[str(sess_id)] = {
                "a_t": round(a_t, 3),
                "b_age_measured": round(b_age, 4),
                "b_age_race_equiv": round(b_age_race, 4),
                "r2_time": r2_t,
                "n_time_laps": int(len(td)),
                "dominant_mode": dominant_mode,
                "scale_factor": round(scale, 2),
            }

        # Condiciones ambientales medias
        temp_mean = (
            round(float(grp["trackTemp"].mean()), 1)
            if "trackTemp" in grp.columns and grp["trackTemp"].notna().any()
            else None
        )
        rubber_mean = (
            round(float(grp["rubber"].mean()), 4)
            if "rubber" in grp.columns and grp["rubber"].notna().any()
            else None
        )

        # Coeficientes finales del modelo guardado
        model_coeffs = models.get(comp)
        model_entry: dict = {}
        if model_coeffs is not None:
            keys = ["a", "b_age", "c_fuel", "d_temp"][: len(model_coeffs)]
            model_entry = {k: round(float(v), 5) for k, v in zip(keys, model_coeffs)}

        # Construir entrada
        entry: dict = {
            "saved_at": today,
            "compound": comp,
            "dominant_mode": dominant_mode,
            "scale_factor": round(scale, 2),
            **b_w_entry,
            "time_by_session": time_entries,
            "model_coefficients": model_entry,
            "conditions": {
                "track_temp_mean_c": temp_mean,
                "rubber_mean": rubber_mean,
            },
        }

        # Acumular en db: db[track][driver][compound] es una lista de entradas
        db.setdefault(track, {}).setdefault(driver, {}).setdefault(comp, [])

        # Sobreescribir si ya existe una entrada del mismo día, si no añadir
        existing = db[track][driver][comp]
        replaced = False
        for i, old in enumerate(existing):
            if old.get("saved_at") == today:
                existing[i] = entry
                replaced = True
                break
        if not replaced:
            existing.append(entry)

    out_path.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Calibración de escala a partir de datos históricos
# ---------------------------------------------------------------------------

# Sesiones consideradas "carrera" para calibrar el factor real
_RACE_SESSIONS = {"Race", "Sprint"}
# Modos de carrera que representan ritmo real
_RACE_PACE_MODES = {"Standard", "Aggressive", "Attack"}
# R² mínimo para considerar un ajuste de desgaste fiable
_MIN_R2_WEAR = 0.80
# Número mínimo de laps para considerar una entrada fiable
_MIN_LAPS = 5


def get_driver_scale(
    research_root: Path,
    driver: str,
    compound: str,
    practice_mode: str,
) -> float:
    """Devuelve el factor de escala calibrado para convertir b_w de práctica
    al equivalente de ritmo de carrera para este piloto y compuesto.

    Proceso:
      1. Lee todas las entradas de carrera (Race/Sprint) del piloto para ese
         compuesto en cualquier circuito — modo dominante Standard/Aggressive.
      2. Lee todas las entradas de práctica del mismo compuesto con el mismo
         practice_mode (ej. "Light").
      3. Calcula el ratio real b_w_carrera / b_w_practica por circuito donde
         coincidan ambas entradas y promedia los ratios con peso R².
      4. Si no hay datos suficientes, devuelve el valor por defecto de
         PACE_WEAR_SCALE[practice_mode].

    Args:
        research_root: Directorio donde está tire_behavior.json.
        driver: Nombre del piloto (ej. "Fernando Alonso").
        compound: Compuesto canonicalizado (ej. "Soft").
        practice_mode: Modo dominante de la práctica (ej. "Light").

    Returns:
        Factor de escala calibrado (≥ 1.0). Cuanto mayor, más conservativa
        fue la práctica respecto a la carrera real.
    """
    fallback = PACE_WEAR_SCALE.get(practice_mode, 1.0)

    json_path = research_root / "tire_behavior.json"
    if not json_path.exists():
        return fallback

    try:
        db: dict = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback

    compound = canonical_compound(compound)

    # Recopilar pares (b_w_practice, b_w_race, weight=r2) por circuito
    ratios: list[float] = []
    weights: list[float] = []

    for track, track_data in db.items():
        driver_data = track_data.get(driver, {})
        comp_entries = driver_data.get(compound, [])

        # Entradas de práctica con el modo dado y r2 suficiente
        practice_entries = [
            e for e in comp_entries
            if e.get("dominant_mode") == practice_mode
            and abs(e.get("b_w_measured", 0.0)) >= MIN_WEAR_RATE_PER_LAP
            and e.get("r2_wear", 0.0) >= _MIN_R2_WEAR
            and e.get("n_wear_laps", 0) >= _MIN_LAPS
        ]

        # Entradas de carrera: sesiones Race/Sprint con modo Standard/Aggressive
        race_entries = [
            e for e in comp_entries
            if e.get("dominant_mode") in _RACE_PACE_MODES
            and abs(e.get("b_w_measured", 0.0)) >= MIN_WEAR_RATE_PER_LAP
            and e.get("r2_wear", 0.0) >= _MIN_R2_WEAR
            and e.get("n_wear_laps", 0) >= _MIN_LAPS
        ]

        if not practice_entries or not race_entries:
            continue

        # Usar los valores más recientes de cada tipo para ese circuito
        p = sorted(practice_entries, key=lambda x: x.get("saved_at", ""))[-1]
        r = sorted(race_entries, key=lambda x: x.get("saved_at", ""))[-1]

        b_w_p = abs(float(p["b_w_measured"]))
        b_w_r = abs(float(r["b_w_measured"]))

        if b_w_p < MIN_WEAR_RATE_PER_LAP:
            continue

        ratio = b_w_r / b_w_p
        # Peso combinado: raíz del producto de los R² de ambas entradas
        weight = float(p.get("r2_wear", 0.5)) * float(r.get("r2_wear", 0.5))

        ratios.append(ratio)
        weights.append(weight)

    if not ratios:
        return fallback

    # Media ponderada de los ratios
    total_w = sum(weights)
    if total_w == 0:
        return fallback

    calibrated = sum(r * w for r, w in zip(ratios, weights)) / total_w
    # Clamp: mínimo 0.8 (práctica más agresiva que carrera, caso raro)
    # máximo 4.0 (práctica extremadamente conservativa)
    return round(max(0.8, min(4.0, calibrated)), 3)

