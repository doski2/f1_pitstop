"""Render function for the Strategy tab."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from _data import (
    fit_degradation_models,
    generate_race_plans,
    load_practice_data,
    load_precomputed_model,
    save_model_json,
)
from _imports import COL_LAP, COL_LAP_TIME, live_pit_recommendation

TRACK_LAPS: dict[str, int] = {
    "Bahrain": 57,
    "Monaco": 78,
    "Monza": 53,
    "Spa": 44,
    "Silverstone": 52,
    "Barcelona": 66,
    "Suzuka": 53,
    "Canada": 70,
    "Brazil": 71,
    "Abu Dhabi": 58,
    "SaudiArabia": 50,
}


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
    st.markdown("### Planificación de Estrategia (Combustible y Degradación)")
    is_race = "race" in session.lower()
    models: dict = {}

    practice_data = load_practice_data(data_root, track, driver)
    fallback_used = False
    if practice_data.empty and is_race and not lap_summary.empty:
        if st.checkbox(
            "Sin prácticas. Usar vueltas iniciales de carrera como estimación provisoria"
        ):
            initial = lap_summary[lap_summary[COL_LAP_TIME].notna()].nsmallest(
                12, COL_LAP
            )
            cols_base = ["compound", "tire_age", "lap_time_s"]
            if "fuel" in initial.columns:
                cols_base.append("fuel")
            practice_data = initial[cols_base].copy()
            practice_data["session"] = "RaceSample"
            fallback_used = True

    if practice_data.empty:
        st.info("No hay datos suficientes para modelar.")
        return models

    col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 1])
    use_fuel = col_f1.checkbox("Usar combustible", value=True)

    # Auto-cálculo combustible inicial
    if "auto_start_fuel" not in st.session_state:
        st.session_state["auto_start_fuel"] = None
    if (
        col_f2.button("Auto inicial", help="Detectar combustible inicial desde datos")
        and use_fuel
        and "fuel" in practice_data.columns
    ):
        valid_fuel = practice_data["fuel"].dropna()
        if len(valid_fuel) >= 3:
            calc_val = float(valid_fuel.max())
            st.session_state["auto_start_fuel"] = calc_val
            st.session_state["start_fuel_input"] = calc_val

    default_start_fuel = (
        st.session_state["auto_start_fuel"]
        if st.session_state.get("auto_start_fuel") is not None
        else (
            float(practice_data["fuel"].max())
            if use_fuel
            and "fuel" in practice_data.columns
            and practice_data["fuel"].notna().any()
            else 100.0
        )
    )
    start_fuel = col_f2.number_input(
        "Combustible inicial (kg)",
        value=default_start_fuel,
        min_value=0.0,
        key="start_fuel_input",
    )

    # Auto-cálculo consumo
    if "cons_per_lap_override" not in st.session_state:
        st.session_state["cons_per_lap_override"] = None
    if (
        col_f4.button(
            "Auto consumo",
            help="Estimar consumo medio por vuelta usando diferencias de fuel",
        )
        and use_fuel
        and "fuel" in practice_data.columns
    ):
        fuel_series = practice_data["fuel"].dropna().sort_index()
        if len(fuel_series) >= 5:
            diffs: pd.Series = (
                pd.to_numeric((-fuel_series.diff()).dropna(), errors="coerce")
                .dropna()
                .astype(float)
            )
            plausible = diffs[(diffs > 0) & (diffs < 5)]
            if len(plausible) >= 3:
                calc_cons = float(plausible.median())
                st.session_state["cons_per_lap_override"] = calc_cons
                st.session_state["cons_input"] = calc_cons
            else:
                st.warning(
                    "Insuficientes diferencias plausibles de fuel para estimar consumo; usando valor base."
                )

    base_cons = 1.4
    if (
        use_fuel
        and "fuel" in practice_data.columns
        and practice_data["fuel"].notna().sum() > 3
    ):
        base_cons = float(practice_data["fuel"].diff().abs().median()) or base_cons
    if st.session_state.get("cons_per_lap_override") is not None:
        base_cons = st.session_state["cons_per_lap_override"]
    cons_per_lap = col_f3.number_input(
        "Consumo por vuelta (kg)",
        value=base_cons,
        min_value=0.0,
        format="%.3f",
        key="cons_input",
    )
    if use_fuel and st.session_state.get("cons_per_lap_override") is not None:
        st.caption(
            f"Consumo auto-estimado: {st.session_state['cons_per_lap_override']:.3f} kg/v"
        )

    use_pre = st.checkbox("Usar modelo precomputado (si existe)", value=True)
    pre_models: dict = {}
    pre_meta: dict = {}
    if use_pre:
        pre_models, pre_meta = load_precomputed_model(models_root, track, driver)
        if pre_models:
            st.caption(
                f"Modelo precomputado cargado (fuel_used={pre_meta.get('fuel_used')})"
            )

    models = pre_models if pre_models else fit_degradation_models(practice_data)

    if not models:
        st.warning("Modelos no generados (datos insuficientes).")
        return models

    if fallback_used:
        st.warning("Modelo generado con vueltas de carrera (provisional).")

    model_rows = []
    for comp, coeffs in models.items():
        if len(coeffs) == 3:
            a, b_age, c_fuel = coeffs
            model_rows.append(
                {
                    "Compuesto": comp,
                    "a": round(a, 3),
                    "b_age": round(b_age, 4),
                    "c_fuel": round(c_fuel, 4),
                }
            )
        else:
            a, b_age = coeffs
            model_rows.append(
                {"Compuesto": comp, "a": round(a, 3), "b_age": round(b_age, 4), "c_fuel": None}
            )
    st.dataframe(pd.DataFrame(model_rows), use_container_width=True)

    col_sv1, _ = st.columns([1, 3])
    if col_sv1.button("Guardar modelo"):
        sessions_used = (
            sorted(practice_data["session"].unique())
            if "session" in practice_data.columns
            else []
        )
        fuel_used = any(len(v) == 3 for v in models.values())
        save_model_json(
            models_root, track, driver, models, sessions_used, fuel_used, app_version
        )

    total_race_laps_real = TRACK_LAPS.get(track, 57)
    completed_laps = int(lap_summary[COL_LAP].max()) if not lap_summary.empty else 0

    col_rl1, col_rl2 = st.columns([1, 2])
    use_completed = col_rl1.checkbox(
        "Usar vueltas completadas",
        value=is_race,
        help="Si activo, la estrategia usa sólo las vueltas ya registradas.",
    )
    if use_completed:
        race_laps_horizon = max(completed_laps, 1)
        col_rl2.markdown(f"**Vueltas para cálculo:** {race_laps_horizon} (parcial)")
    else:
        race_laps_horizon = col_rl2.number_input(
            "Vueltas totales carrera",
            value=total_race_laps_real,
            min_value=completed_laps if completed_laps > 0 else 10,
            max_value=110,
        )
        if race_laps_horizon < completed_laps:
            st.warning(
                "El total indicado es menor que vueltas ya completadas; se usará número de vueltas completadas."
            )
            race_laps_horizon = completed_laps

    pit_loss = st.number_input(
        "Pérdida pit stop (s)", value=22.0, min_value=5.0, max_value=60.0, step=0.5
    )
    max_stops = st.slider("Paradas máximas", 0, 4, 2)
    min_stint = st.slider("Stint mínimo (vueltas)", 3, 20, 5)
    require_two = st.checkbox("Requerir dos compuestos (seco)", value=True)

    if st.button("Calcular Estrategias"):
        plans = generate_race_plans(
            race_laps_horizon,
            list(models.keys()),
            models,
            practice_data,
            pit_loss,
            max_stops=max_stops,
            min_stint=min_stint,
            require_two_compounds=require_two,
            use_fuel=use_fuel,
            start_fuel=start_fuel,
            cons_per_lap=cons_per_lap,
        )
        if not plans:
            st.warning("No se generaron planes.")
        else:
            for i, p in enumerate(plans, 1):
                st.markdown(
                    f"**Plan {i}** Tiempo total: {p['total_time']:.2f}s | Paradas: {p['stops']}"
                )
                stint_rows = []
                acc = 0
                for idx_s, s in enumerate(p["stints"], 1):
                    start_l = acc + 1
                    end_l = acc + s["laps"]
                    acc = end_l
                    stint_rows.append(
                        {
                            "#": idx_s,
                            "Compuesto": s["compound"],
                            "Vueltas": s["laps"],
                            "Rango": f"{start_l}-{end_l}",
                            "Tiempo Est. (s)": round(s["pred_time"], 2),
                        }
                    )
                st.dataframe(pd.DataFrame(stint_rows), use_container_width=True)

    if is_race and not lap_summary.empty:
        st.markdown("---")
        st.subheader("Recomendación en Vivo")
        if COL_LAP in lap_summary.columns:
            current_lap = int(lap_summary[COL_LAP].max())
            last_row = lap_summary[lap_summary[COL_LAP] == current_lap].tail(1)
            comp_now = (
                last_row["compound"].iloc[0]
                if not last_row.empty and "compound" in last_row.columns
                else None
            )
            age_now = (
                int(last_row["tire_age"].iloc[0])
                if not last_row.empty and "tire_age" in last_row.columns
                else 0
            )
            current_fuel = (
                float(last_row["fuel"].iloc[0])
                if use_fuel and "fuel" in last_row.columns and not last_row.empty
                else start_fuel
            )
            rec = (
                live_pit_recommendation(
                    current_lap,
                    total_race_laps_real,
                    str(comp_now),
                    age_now,
                    models,
                    practice_data,
                    pit_loss,
                    use_fuel=use_fuel,
                    current_fuel=current_fuel,
                    cons_per_lap=cons_per_lap,
                )
                if comp_now
                else None
            )
            if rec:
                st.success(
                    f"Parar en vuelta {rec['pit_on_lap']} (seguir {rec['continue_laps']}) "
                    f"-> {rec['new_compound']} | "
                    f"Tiempo restante: {rec['projected_total_remaining']:.1f}s"
                )
            else:
                st.info("Sin recomendación disponible.")
        else:
            st.info("No hay datos de vuelta actual disponibles.")
    else:
        st.info("No hay datos de telemetría disponibles para recomendaciones en vivo.")

    return models
