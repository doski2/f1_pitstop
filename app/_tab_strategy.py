"""Render function for the Strategy tab.

Two-phase design:
  A. Modelo        — build degradation model from FP1+FP2+FP3 (+ live race laps)
  B. Parámetros    — manual inputs: track temp, pit loss, stops (2/3), fuel (auto)
  C. Estrategias   — calculate top plans, user picks one → stored in session_state
  D. Seguimiento   — live state vs chosen plan (race session only)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from _data import (
    fit_combined_model,
    fit_degradation_models,
    generate_race_plans,
    load_practice_data,
    load_precomputed_model,
    save_model_json,
)
from _imports import (
    COL_LAP,
    display_compound,
    plan_aware_recommendation,
)

from f1m.research import save_tire_research

# Vueltas por circuito — se usa como valor por defecto editable por el usuario
TRACK_LAPS: dict[str, int] = {
    "Albert Park": 58,
    "Bahrain": 57,
    "Shanghai": 56,
    "Baku": 51,
    "Barcelona": 66,
    "Monaco": 78,
    "Montreal": 70,
    "Paul Ricard": 53,
    "Red Bull Ring": 71,
    "Silverstone": 52,
    "Jeddah": 50,
    "Hungaroring": 70,
    "Spa-Francorchamps": 44,
    "Monza": 53,
    "Marina Bay": 62,
    "Sochi": 53,
    "Suzuka": 53,
    "Hermanos Rodriguez": 71,
    "Circuit of the Americas": 56,
    "Interlagos": 71,
    "Yas Marina": 58,
    "Miami": 57,
    "Zandvoort": 72,
    "Imola": 63,
    "Las Vegas": 50,
    "Qatar": 57,
}

# Stint mínimo fijo — no visible al usuario, evita stints de 1-2 vueltas sin sentido
_MIN_STINT_FIXED = 3


def _infer_fuel_cons(df: pd.DataFrame) -> tuple[float, float]:
    """Auto-infer starting fuel (kg) and consumption per lap (kg/v) from telemetry."""
    if "fuel" not in df.columns or df["fuel"].isna().all():
        return 100.0, 1.4
    valid = df["fuel"].dropna()
    start_fuel = float(valid.max())
    # Prefer fuelDelta when available — direct per-lap reading from the game.
    # Guard with a plausible range (0.3–5.0 kg/lap) to reject per-sample noise.
    if "fuelDelta" in df.columns:
        delta_vals = pd.to_numeric(df["fuelDelta"], errors="coerce").abs().dropna()
        plausible_delta = delta_vals[(delta_vals > 0.3) & (delta_vals < 5.0)]
        if len(plausible_delta) >= 3:
            return start_fuel, float(plausible_delta.median())
    # Fallback: derive consumption from differences in fuel level
    diffs = pd.to_numeric(
        (-valid.sort_index().diff()).dropna(), errors="coerce"
    ).dropna()
    plausible = diffs[(diffs > 0.05) & (diffs < 5.0)]
    cons = float(plausible.median()) if len(plausible) >= 3 else 1.4
    return start_fuel, cons


def render_strategy_tab(
    track: str,
    session: str,
    driver: str,
    lap_summary: pd.DataFrame,
    data_root: Path,
    models_root: Path,
    app_version: str,
) -> dict:
    """Renderiza el tab de Estrategia. Devuelve el dict de modelos ajustados."""
    is_race = "race" in session.lower()
    has_race_data = is_race and not lap_summary.empty
    models: dict = {}

    # ── A. MODELO ──────────────────────────────────────────────────────────
    st.subheader("A · Modelo de degradación")

    # Carga de prácticas FP1/FP2/FP3 siempre
    # _data_version = max mtime de los parquets curados → invalida caché cuando se re-cura
    from pathlib import Path as _Path

    _curated_root = _Path("curated") / f"track={track}"
    _data_version = max(
        (p.stat().st_mtime for p in _curated_root.rglob("laps.parquet") if p.exists()),
        default=0.0,
    )
    practice_data = load_practice_data(
        data_root, track, driver, _data_version=_data_version
    )

    # En carrera: extraer vueltas de carrera para blend con prácticas
    race_laps_extra: pd.DataFrame | None = None
    if has_race_data:
        _race_cols = [
            c
            for c in [
                "compound",
                "tire_age",
                "lap_time_s",
                "fuel",
                "trackTemp",
                "pit_stop",
                "safety_car",
                "rain",
                "session",
            ]
            if c in lap_summary.columns
        ]
        race_laps_extra = lap_summary[_race_cols].copy()
        if "session" not in race_laps_extra.columns:
            race_laps_extra["session"] = "Race"
        st.caption(
            f"Carrera activa — {len(race_laps_extra)} filas de carrera "
            "se usan como datos primarios (2× peso en el modelo)."
        )

    # Dataset combinado: prácticas base + vueltas de carrera con 2× peso
    combined_data = fit_combined_model(practice_data, race_laps_extra)
    if combined_data.empty:
        st.info("Sin datos de entrenamiento libre ni de carrera para modelar.")
        return models

    # Fuente del modelo
    use_pre = st.checkbox(
        "Usar modelo guardado (si existe)",
        value=True,
        key="use_pre",
        help="Si no hay datos de carrera activos, el modelo guardado se usa directamente.",
    )
    pre_models, pre_meta = {}, {}
    if use_pre:
        pre_models, pre_meta = load_precomputed_model(models_root, track, driver)
        if pre_models:
            st.caption(
                f"Modelo guardado: fuel={pre_meta.get('fuel_used')}, "
                f"temp={pre_meta.get('temp_used', False)}, "
                f"sesiones={pre_meta.get('sessions_included', [])}"
            )

    # Con datos de carrera activos siempre reajustamos para capturar ritmo real
    if pre_models and not has_race_data:
        models = pre_models
    else:
        models = fit_degradation_models(combined_data)

    if not models:
        st.warning("Datos insuficientes para generar modelos de degradación.")
        return models

    with st.expander("Ver coeficientes del modelo", expanded=False):
        model_rows = []
        for comp, coeffs in models.items():
            row: dict = {
                "Compuesto": display_compound(comp),
                "a (base s)": round(coeffs[0], 3),
                "b_age (s/v)": round(coeffs[1], 4),
            }
            if len(coeffs) >= 3:
                row["c_fuel"] = round(coeffs[2], 4) if coeffs[2] != 0.0 else "—"
            if len(coeffs) == 4:
                row["d_temp"] = round(coeffs[3], 5)
            # sessions contributing
            if "session" in combined_data.columns:
                sessions_list = sorted(combined_data["session"].unique().tolist())
                row["Sesiones"] = ", ".join(str(s) for s in sessions_list)
            model_rows.append(row)
        st.dataframe(pd.DataFrame(model_rows), width="stretch")

    col_sv, _ = st.columns([1, 4])
    if col_sv.button("Guardar modelo", key="save_model_btn"):
        sessions_used = (
            sorted(combined_data["session"].unique().tolist())
            if "session" in combined_data.columns
            else []
        )
        fuel_used = any(
            (len(v) == 3) or (len(v) == 4 and v[2] != 0.0) for v in models.values()
        )
        temp_used = any(len(v) == 4 for v in models.values())
        save_model_json(
            models_root,
            track,
            driver,
            models,
            sessions_used,
            fuel_used,
            app_version,
            temp_used,
        )
        research_root = Path("research")
        save_tire_research(research_root, track, driver, combined_data, models)
        st.info(
            "Investigacion de neumaticos actualizada en research/tire_behavior.json"
        )

    # ── B. PARÁMETROS DE CARRERA ───────────────────────────────────────────
    st.subheader("B · Parámetros de carrera")

    col_b1, col_b2, col_b3 = st.columns(3)

    # Temperatura de pista (manual — el usuario la introduce)
    _avg_temp = (
        float(practice_data["trackTemp"].mean())
        if "trackTemp" in practice_data.columns
        and practice_data["trackTemp"].notna().any()
        else 40.0
    )
    use_temp_model = any(len(v) == 4 for v in models.values())
    race_temp = 0.0
    if use_temp_model:
        race_temp = col_b1.number_input(
            "Temperatura pista (°C)",
            value=_avg_temp,
            min_value=10.0,
            max_value=80.0,
            step=1.0,
            key="race_temp_input",
        )
        col_b1.caption(f"Media prácticas: {_avg_temp:.0f} °C")
    else:
        col_b1.metric("Temp. media prácticas", f"{_avg_temp:.0f} °C")

    # Pérdida pit stop (manual)
    pit_loss = col_b2.number_input(
        "Pérdida pit stop (s)",
        value=22.0,
        min_value=5.0,
        max_value=60.0,
        step=0.5,
        key="pit_loss",
    )

    # Paradas: 1 o 2 paradas EN CARRERA (elección de ruedas de salida no cuenta)
    max_stops: int = col_b3.radio(  # type: ignore[assignment]
        "Paradas en carrera",
        options=[1, 2],
        format_func=lambda n: f"{n} parada" if n == 1 else f"{n} paradas",
        index=1,
        horizontal=True,
        key="max_stops",
        help="Paradas durante la carrera. La elección de neumáticos de salida no cuenta.",
    )

    # Combustible — auto-detectado de carrera si disponible, si no de prácticas
    _fuel_source = (
        race_laps_extra
        if race_laps_extra is not None and not race_laps_extra.empty
        else practice_data
    )
    _auto_fuel, _auto_cons = _infer_fuel_cons(_fuel_source)
    use_fuel = (
        "fuel" in combined_data.columns and combined_data["fuel"].notna().sum() >= 3
    )

    col_c1, col_c2 = st.columns(2)
    start_fuel = col_c1.number_input(
        "Combustible inicial (kg)",
        value=_auto_fuel,
        min_value=0.0,
        key="start_fuel_input",
        help="Auto-detectado del valor máximo de fuel registrado.",
        disabled=not use_fuel,
    )
    cons_per_lap = col_c2.number_input(
        "Consumo por vuelta (kg)",
        value=round(_auto_cons, 3),
        min_value=0.0,
        format="%.3f",
        key="cons_input",
        help="Auto-estimado de la mediana de diferencias de fuel.",
        disabled=not use_fuel,
    )
    if not use_fuel:
        st.caption("Sin datos de combustible — planificación por degradación pura.")

    # Lluvia — auto-detectada, editable
    _rain_detected = False
    for _df in [practice_data, lap_summary]:
        if not _df.empty and "rain" in _df.columns:
            if bool(_df["rain"].fillna(False).any()):
                _rain_detected = True
                break
    is_wet = st.checkbox(
        "Carrera en condiciones de lluvia (sin obligación de 2 compuestos)",
        value=_rain_detected,
        key="is_wet",
    )
    require_two = not is_wet

    # Vueltas totales
    total_race_laps: int = st.number_input(  # type: ignore[assignment]
        "Vueltas totales de carrera",
        value=TRACK_LAPS.get(track, 57),
        min_value=5,
        max_value=115,
        key="race_laps_input",
    )

    # ── C. ESTRATEGIAS ────────────────────────────────────────────────────
    st.subheader("C · Estrategias calculadas")

    if st.button("Calcular estrategias", key="calc_strategies"):
        try:
            plans = generate_race_plans(
                int(total_race_laps),
                list(models.keys()),
                models,
                combined_data,
                float(pit_loss),
                max_stops=int(max_stops),
                exact_stops=True,
                min_stint=_MIN_STINT_FIXED,
                require_two_compounds=require_two,
                use_fuel=use_fuel,
                start_fuel=float(start_fuel),
                cons_per_lap=float(cons_per_lap),
                race_temp=float(race_temp),
                driver=driver,
                research_root=Path("research"),
            )
            st.session_state["race_plans"] = plans
            # Reset plan selection on new calculation
            for _k in ("chosen_plan_radio", "chosen_plan", "race_params"):
                st.session_state.pop(_k, None)
            if not plans:
                st.warning(
                    f"No se encontraron planes con exactamente {max_stops} parada(s). "
                    f"Compuestos disponibles: {list(models.keys())} | "
                    f"Vueltas: {total_race_laps} | "
                    f"2 compuestos requeridos: {require_two}"
                )
        except Exception as exc:
            st.error(f"Error calculando estrategias: {type(exc).__name__}: {exc}")

    plans: list = st.session_state.get("race_plans", [])

    if not plans:
        st.info("Pulsa **Calcular estrategias** para ver las opciones.")
    else:
        # Build display labels
        plan_labels: list[str] = []
        for i, p in enumerate(plans, 1):
            stint_parts = " → ".join(
                f"{display_compound(s['compound'])} {s['laps']}v" for s in p["stints"]
            )
            plan_labels.append(
                f"Plan {i} | {p['total_time']:.0f}s | {p['stops']} parada(s) | {stint_parts}"
            )

        chosen_idx: int = st.radio(  # type: ignore[assignment]
            "Elige la estrategia a seguir",
            options=list(range(len(plans))),
            format_func=lambda i: plan_labels[i],
            key="chosen_plan_radio",
        )

        # Persist chosen plan and params
        chosen_plan = plans[chosen_idx]
        st.session_state["chosen_plan"] = chosen_plan
        st.session_state["race_params"] = {
            "total_race_laps": int(total_race_laps),
            "pit_loss": float(pit_loss),
            "use_fuel": use_fuel,
            "start_fuel": float(start_fuel),
            "cons_per_lap": float(cons_per_lap),
            "race_temp": float(race_temp),
        }

        # Stint detail table
        stint_rows = []
        acc = 0
        for idx_s, s in enumerate(chosen_plan["stints"], 1):
            start_l = acc + 1
            end_l = acc + s["laps"]
            acc = end_l
            stint_rows.append(
                {
                    "#": idx_s,
                    "Compuesto": display_compound(s["compound"]),
                    "Vueltas": s["laps"],
                    "Rango": f"V{start_l}–V{end_l}",
                    "Tiempo Est. (s)": round(s["pred_time"], 2),
                }
            )
        st.dataframe(pd.DataFrame(stint_rows), width="stretch")

    # ── D. SEGUIMIENTO EN VIVO ────────────────────────────────────────────
    if has_race_data:
        st.markdown("---")
        st.subheader("D · Seguimiento en carrera")

        chosen_plan_live = st.session_state.get("chosen_plan")
        race_params = st.session_state.get("race_params", {})

        # Estado actual del coche
        current_lap = (
            int(lap_summary[COL_LAP].max()) if COL_LAP in lap_summary.columns else 0
        )
        last_row = lap_summary[lap_summary[COL_LAP] == current_lap].tail(1)
        comp_now = (
            str(last_row["compound"].iloc[0])
            if not last_row.empty and "compound" in last_row.columns
            else None
        )
        age_now = (
            int(last_row["tire_age"].iloc[0])
            if not last_row.empty and "tire_age" in last_row.columns
            else 0
        )
        current_fuel_live = (
            float(last_row["fuel"].iloc[0])
            if use_fuel and not last_row.empty and "fuel" in last_row.columns
            else float(start_fuel)
        )
        total_laps_live = race_params.get("total_race_laps", int(total_race_laps))
        rem = max(0, total_laps_live - current_lap)

        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        col_d1.metric("Vuelta actual", current_lap)
        col_d2.metric("Compuesto", display_compound(comp_now) if comp_now else "?")
        col_d3.metric("Edad neumático", f"{age_now} v")
        col_d4.metric("Vueltas restantes", rem)

        if not chosen_plan_live:
            st.info(
                "Selecciona una estrategia en la sección C para activar el seguimiento."
            )
        elif not comp_now:
            st.info("Sin datos de compuesto actual en la telemetría.")
        else:
            rec = plan_aware_recommendation(
                current_lap=current_lap,
                total_race_laps=total_laps_live,
                current_compound=comp_now,
                current_tire_age=age_now,
                models=models,
                chosen_plan=chosen_plan_live["stints"],
                practice_laps=combined_data,
                pit_loss=race_params.get("pit_loss", float(pit_loss)),
                window=5,
                use_fuel=race_params.get("use_fuel", use_fuel),
                current_fuel=current_fuel_live,
                cons_per_lap=race_params.get("cons_per_lap", float(cons_per_lap)),
                race_temp=race_params.get("race_temp", float(race_temp)),
            )

            if rec is None:
                st.warning(
                    f"Sin recomendación — '{display_compound(comp_now)}' no está en el modelo "
                    "o carrera terminada."
                )
            elif rec["status"] == "finished":
                st.success("Carrera completada.")
            elif rec["status"] == "last_stint":
                st.success(
                    f"Último stint — sin más paradas planificadas. "
                    f"Compuesto: **{display_compound(comp_now)}** · {rem} vueltas restantes."
                )
            elif rec["status"] == "on_plan":
                st.success(
                    f"En plan — parada prevista: **V{rec['planned_pit_lap']}** "
                    f"→ {rec['next_compound']}"
                )
            elif rec["status"] == "pit_earlier":
                delta = rec["planned_pit_lap"] - rec["recommended_pit_lap"]
                st.warning(
                    f"Ritmo más lento — parar **{delta} vuelta(s) antes**: "
                    f"**V{rec['recommended_pit_lap']}** (plan: V{rec['planned_pit_lap']}) "
                    f"→ {rec['next_compound']} · Ganancia: **{rec['time_saving']:.1f}s**"
                )
            elif rec["status"] == "pit_later":
                delta = rec["recommended_pit_lap"] - rec["planned_pit_lap"]
                st.info(
                    f"Ritmo mejor — aguantar **{delta} vuelta(s) más**: "
                    f"**V{rec['recommended_pit_lap']}** (plan: V{rec['planned_pit_lap']}) "
                    f"→ {rec['next_compound']} · Beneficio: **{rec['time_saving']:.1f}s**"
                )

    return models
