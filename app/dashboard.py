"""Dashboard principal de estrategia.

_imports.py inserta el directorio raíz del proyecto en sys.path antes de importar
los módulos f1m, por lo que este archivo no necesita manipular sys.path directamente.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import streamlit as st
from _charts import (
    create_compound_evolution_chart,
    create_lap_times_chart,
    create_temperatures_chart,
)
from _data import (
    fit_degradation_models,
    generate_race_plans,
    load_and_process,
    load_practice_data,
    load_precomputed_model,
    save_model_json,
)

# _imports.py realiza el sys.path fix y re-exporta todos los símbolos de f1m.
from _imports import (
    _PLOTLY_AVAILABLE,
    COL_LAP,
    COL_LAP_TIME,
    COL_RAIN,
    COL_SAFETY_CAR,
    DIR_MODELS,
    adjust_lap_time_for_conditions,
    go,
    live_pit_recommendation,
    px,
)
from _metrics import calculate_consistency_metrics, calculate_model_metrics

# TODO: fuel-aware modeling integration in subsequent iteration


st.set_page_config(page_title="Estrategia Pit Stop F1 Manager 2024", layout="wide")

APP_VERSION = "1.2.0"


# --- Utilidad para componer cadenas con tipos mixtos (p. ej., numpy object, Path, etc.) ---
def _join_str(items: Iterable[object], sep: str = ", ") -> str:
    return sep.join(str(x) for x in items)


# --- Guardas de sesión para evitar re-ejecuciones en cascada ---
if "init_done" not in st.session_state:
    st.session_state["init_done"] = True
if "auto_guard" not in st.session_state:
    st.session_state["auto_guard"] = False
st.title("Dashboard Estrategia de Paradas – F1 Manager 2024")
st.caption(
    "Análisis de telemetría, stints, temperaturas y cumplimiento normativo FIA (simplificado)"
)
st.sidebar.markdown(f"**Versión:** {APP_VERSION}")

BASE_DIR = (
    Path(__file__).resolve().parent
)  # raíz del proyecto (robusto para streamlit run)
_candidate_paths = [
    Path("logs_in/exported_data"),  # relativo al cwd
    BASE_DIR / "logs_in" / "exported_data",  # relativo al archivo
]
DATA_ROOT = None
for cand in _candidate_paths:
    if cand.exists():
        DATA_ROOT = cand
        break
if DATA_ROOT is None:
    st.error(
        "No se encontró la carpeta de datos en rutas intentadas:\n"
        + _join_str([str(p.resolve()) for p in _candidate_paths], sep="\n")
    )
    st.stop()

# Assertion for mypy: st.stop() prevents execution beyond this point
assert DATA_ROOT is not None

MODELS_ROOT = BASE_DIR / DIR_MODELS

# ---------- sidebar selectors ----------
# Selección jerárquica: Circuito -> Sesión -> Piloto -> Archivo
tracks = sorted({p.name for p in DATA_ROOT.iterdir() if p.is_dir()})
track: str = st.sidebar.selectbox("Circuito", tracks)
st.sidebar.caption("Origen datos: F1 Manager 2024 (adapter)")

session_root = DATA_ROOT / track
sessions = [p.name for p in session_root.iterdir() if p.is_dir()]
session: str = st.sidebar.selectbox("Sesión", sorted(sessions))

driver_root = session_root / session
drivers = []
for d in driver_root.rglob("*"):  # allow deeper structure (driver folders)
    if d.is_dir() and any(f.suffix == ".csv" for f in d.glob("*.csv")):
        drivers.append(d.name)
drivers = sorted(set(drivers))
if not drivers:
    st.warning("No hay pilotos con datos.")
    st.stop()

driver: Optional[str] = st.sidebar.selectbox("Piloto", drivers)
assert driver is not None and isinstance(driver, str)

driver_dir = driver_root / driver
csv_files = sorted(driver_dir.glob("*.csv"))
if not csv_files:
    st.warning("No hay archivos CSV para este piloto.")
    st.stop()

selected_csv: Optional[str] = st.sidebar.selectbox(
    "Archivo Telemetría", [f.name for f in csv_files]
)
assert selected_csv is not None and isinstance(selected_csv, str)
# At this point selected_csv is narrowed to `str` by the assertion
csv_path = driver_dir / selected_csv


file_mtime = csv_path.stat().st_mtime

col_refresh_a, col_refresh_b, col_refresh_c = st.sidebar.columns([1, 1, 1])
do_refresh = col_refresh_a.button("Refrescar")
auto_refresh = col_refresh_b.checkbox(
    "Auto", value=False, help="Auto-refrescar cada 15s"
)
if auto_refresh:
    _autoref = getattr(st, "autorefresh", None)
    if callable(_autoref):
        _autoref(interval=15000, key="auto_rfr")
    else:
        # fallback mínimo: intentar experimental_rerun si está disponible
        _rerun = getattr(st, "experimental_rerun", None)
        if callable(_rerun):
            _rerun()
if do_refresh:
    st.cache_data.clear()

df, lap_summary, stints, compliance = load_and_process(csv_path, file_mtime)
st.sidebar.caption(
    f"Modificado: {datetime.fromtimestamp(file_mtime).strftime('%H:%M:%S')}"
)

col_meta1, col_meta2, col_meta3 = st.columns(3)
with col_meta1:
    st.metric(
        "Total Laps (estimado)",
        int(lap_summary[COL_LAP].max() if not lap_summary.empty else 0),
    )
with col_meta2:
    if "compound" in lap_summary:
        comps = lap_summary["compound"].dropna().astype(str).unique().tolist()
        unique_compounds = _join_str(sorted(comps), sep=", ")
    else:
        unique_compounds = "—"
    st.metric("Compuestos", unique_compounds)
with col_meta3:
    st.metric("Paradas detectadas", max(len(stints) - 1, 0))

st.subheader("Resumen de Vueltas")
if lap_summary.empty:
    st.info("Sin datos de vueltas.")
else:
    st.dataframe(lap_summary, use_container_width=True, height=300)

st.subheader("Stints")
if stints:
    stint_df = pd.DataFrame([s.__dict__ for s in stints])
    st.dataframe(stint_df, use_container_width=True)
else:
    st.info("No se detectaron stints")

st.subheader("Cumplimiento Normativa (Simplificado)")
status_cols = st.columns(3)
status_cols[0].markdown(
    f"**Dos compuestos (seco):** {'✅' if compliance['used_two_compounds'] else '❌'}"
)
status_cols[1].markdown(
    f"**Stint razonable:** {'✅' if compliance['max_stint_ok'] else '❌'}"
)
status_cols[2].markdown(
    f"**Paradas suficientes:** {'✅' if compliance['pit_stop_required'] else '❌'}"
)
# --- FIX: manejar 'notes' aunque no sea iterable ---
notes_val = compliance.get("notes")
if notes_val:
    if isinstance(notes_val, (list, tuple, set)):
        st.warning(_join_str([str(n) for n in notes_val], sep="\n"))
    elif isinstance(notes_val, str):
        st.warning(notes_val)
    else:
        # objeto único no iterable
        st.warning(str(notes_val))
st.caption(
    "Reglas simplificadas con fines analíticos; para validación oficial consultar reglamento FIA completo."
)

st.subheader("Gráficos")
if not _PLOTLY_AVAILABLE:
    st.warning(
        "Plotly no está instalado. Instale dependencias: `pip install -r requirements.txt`."
    )
    st.stop()
(
    tab_lap,
    tab_ttemps,
    tab_trackair,
    tab_evol,
    tab_strategy,
    tab_wear,
    tab_metrics,
    tab_histogram,
    tab_consistency,
    tab_compounds,
    tab_conditions,
) = st.tabs(
    [
        "Lap Times",
        "Tº Neumáticos",
        "Tº Pista/Aire",
        "Evolución Compuesto",
        "Estrategia",
        "Desgaste",
        "Métricas Modelo",
        "Histograma",
        "Consistencia",
        "Comparación Compuestos",
        "Condiciones Especiales",
    ]
)

with tab_lap:
    if (
        _PLOTLY_AVAILABLE
        and px is not None
        and not lap_summary.empty
        and "lap_time_s" in lap_summary
    ):
        fig = create_lap_times_chart(lap_summary)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de tiempos de vuelta.")

with tab_ttemps:
    temp_cols = ["flTemp", "frTemp", "rlTemp", "rrTemp"]
    existing = [c for c in temp_cols if c in df.columns]
    if _PLOTLY_AVAILABLE and px is not None and existing:
        melt = df.melt(
            id_vars=["timestamp", COL_LAP],
            value_vars=existing,
            var_name="Rueda",
            value_name="Temp",
        )
        fig2 = px.line(
            melt,
            x="timestamp",
            y="Temp",
            color="Rueda",
            hover_data=[COL_LAP],
            title="Temperaturas de Neumáticos",
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No hay columnas de temperatura de rueda.")

with tab_trackair:
    if (
        _PLOTLY_AVAILABLE
        and go is not None
        and "trackTemp" in df.columns
        and "airTemp" in df.columns
    ):
        fig3 = create_temperatures_chart(df)
        if fig3 is not None:
            st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No hay datos de temperatura de pista/aire.")

with tab_evol:
    if _PLOTLY_AVAILABLE and px is not None and not lap_summary.empty:
        fig4 = create_compound_evolution_chart(lap_summary)
        if fig4 is not None:
            st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Sin datos para mostrar evolución de compuesto.")

with tab_strategy:
    st.markdown("### Planificación de Estrategia (Combustible y Degradación)")
    is_race = "race" in session.lower()
    assert driver is not None
    practice_data = load_practice_data(DATA_ROOT, track, driver)
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
    else:
        col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 1])
        use_fuel = col_f1.checkbox("Usar combustible", value=True)
        # Auto-cálculo combustible inicial
        if "auto_start_fuel" not in st.session_state:
            st.session_state["auto_start_fuel"] = None
        if (
            col_f2.button(
                "Auto inicial", help="Detectar combustible inicial desde datos"
            )
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
                fuel_series: pd.Series = fuel_series
                diffs: pd.Series[float] = (
                    pd.to_numeric((-fuel_series.diff()).dropna(), errors="coerce")
                    .dropna()
                    .astype(float)
                )
                plausible: pd.Series[float] = diffs[(diffs > 0) & (diffs < 5)]
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
        pre_models = {}
        pre_meta = {}
        if use_pre:
            pre_models, pre_meta = load_precomputed_model(MODELS_ROOT, track, driver)
            if pre_models:
                st.caption(
                    f"Modelo precomputado cargado (fuel_used={pre_meta.get('fuel_used')})"
                )
        if pre_models:
            models = pre_models
        else:
            models = fit_degradation_models(practice_data)
        if not models:
            st.warning("Modelos no generados (datos insuficientes).")
        else:
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
                        {
                            "Compuesto": comp,
                            "a": round(a, 3),
                            "b_age": round(b_age, 4),
                            "c_fuel": None,
                        }
                    )
            st.dataframe(pd.DataFrame(model_rows), use_container_width=True)
            col_sv1, col_sv2 = st.columns([1, 3])
            if col_sv1.button("Guardar modelo"):
                sessions_used = (
                    sorted(practice_data["session"].unique())
                    if "session" in practice_data.columns
                    else []
                )
                fuel_used = any(len(v) == 3 for v in models.values())
                save_model_json(
                    MODELS_ROOT,
                    track,
                    driver,
                    models,
                    sessions_used,
                    fuel_used,
                    APP_VERSION,
                )
            # Configuración de vueltas totales de carrera (permitir override aunque la carrera esté en progreso)
            TRACK_LAPS = {
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
                # Nuevo GP: Saudi Arabian (Jeddah) – 50 vueltas (longitud 6.174 km)
                "SaudiArabia": 50,
            }
            total_race_laps_real = TRACK_LAPS.get(track, 57)
            completed_laps = (
                int(lap_summary[COL_LAP].max()) if not lap_summary.empty else 0
            )
            col_rl1, col_rl2 = st.columns([1, 2])
            use_completed = col_rl1.checkbox(
                "Usar vueltas completadas",
                value=True if is_race else False,
                help="Si activo, la estrategia usa sólo las vueltas ya registradas; si lo desactivas puedes planificar toda la distancia.",
            )
            if use_completed:
                race_laps_horizon = max(completed_laps, 1)
                col_rl2.markdown(
                    f"**Vueltas para cálculo:** {race_laps_horizon} (parcial)"
                )
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
                "Pérdida pit stop (s)",
                value=22.0,
                min_value=5.0,
                max_value=60.0,
                step=0.5,
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
                        if use_fuel
                        and "fuel" in last_row.columns
                        and not last_row.empty
                        else start_fuel
                    )
                    if comp_now:
                        rec = live_pit_recommendation(
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
                    else:
                        rec = None
                    if rec:
                        st.success(
                            f"Parar en vuelta {rec['pit_on_lap']} (seguir {rec['continue_laps']}) -> {rec['new_compound']} | Tiempo restante: {rec['projected_total_remaining']:.1f}s"
                        )
                    else:
                        st.info("Sin recomendación disponible.")
                else:
                    st.info("No hay datos de vuelta actual disponibles.")
            else:
                st.info(
                    "No hay datos de telemetría disponibles para recomendaciones en vivo."
                )

with tab_wear:
    if "df" in locals() and df is not None:
        wear_cols = ["flDeg", "frDeg", "rlDeg", "rrDeg"]
        have_wear = [c for c in wear_cols if c in df.columns]
        if not have_wear:
            st.info("No hay columnas de desgaste (flDeg, frDeg, rlDeg, rrDeg).")
        else:
            if _PLOTLY_AVAILABLE and px is not None:
                wear_melt = df.melt(
                    id_vars=["timestamp", COL_LAP],
                    value_vars=have_wear,
                    var_name="Rueda",
                    value_name="Desgaste",
                )
                figw = px.line(
                    wear_melt,
                    x=COL_LAP,
                    y="Desgaste",
                    color="Rueda",
                    title="Desgaste Neumáticos (%)",
                    markers=True,
                )
                st.plotly_chart(figw, use_container_width=True)
                # Resumen por vuelta (última muestra de cada vuelta)
                if not lap_summary.empty:
                    last_per_lap = df.sort_values("timestamp").groupby(COL_LAP).tail(1)
                    cols_present = [c for c in wear_cols if c in last_per_lap.columns]
                    st.dataframe(
                        last_per_lap[[COL_LAP] + cols_present],
                        use_container_width=True,
                        height=300,
                    )
            else:
                st.info("Plotly no disponible para graficar desgaste.")
    else:
        st.info("Carga un archivo CSV para ver datos de desgaste.")

with tab_metrics:
    st.markdown("### Métricas de Calidad del Modelo")
    if models:
        model_metrics = calculate_model_metrics(lap_summary, models)
        if model_metrics:
            # Crear tabla de métricas
            metrics_df = pd.DataFrame.from_dict(model_metrics, orient="index")
            metrics_df = metrics_df.round(4)
            metrics_df.columns = ["MAE (s)", "R²", "Muestras"]
            st.dataframe(metrics_df, use_container_width=True)

            # Interpretación
            st.markdown("**Interpretación:**")
            st.markdown("- **MAE**: Error absoluto medio en segundos (menor es mejor)")
            st.markdown(
                "- **R²**: Coeficiente de determinación (más cercano a 1.0 es mejor)"
            )
            st.markdown("- **Muestras**: Número de puntos de datos usados")

            # Gráfico de residuos si hay suficientes datos
            if (
                len(model_metrics) > 0
                and not lap_summary.empty
                and _PLOTLY_AVAILABLE
                and go is not None
            ):
                st.markdown("### Análisis de Residuos")
                fig_resid = go.Figure()
                for compound, params in models.items():
                    if len(params) >= 2 and compound in lap_summary["compound"].values:
                        compound_data = lap_summary[lap_summary["compound"] == compound]
                        if (
                            not compound_data.empty
                            and "tire_age" in compound_data.columns
                        ):
                            intercept, slope = params[0], params[1]
                            predictions = intercept + slope * compound_data["tire_age"]
                            residuals = compound_data["lap_time_s"] - predictions

                            fig_resid.add_trace(
                                go.Scatter(
                                    x=compound_data["tire_age"],
                                    y=residuals,
                                    mode="markers",
                                    name=f"{compound} residuos",
                                    text=[
                                        f"Vuelta {int(lap)}"
                                        for lap in compound_data[COL_LAP]
                                    ],
                                )
                            )

                fig_resid.update_layout(
                    title="Residuos del Modelo (Tiempo Real - Tiempo Predicho)",
                    xaxis_title="Edad del Neumático",
                    yaxis_title="Residuo (segundos)",
                    showlegend=True,
                )
                st.plotly_chart(fig_resid, use_container_width=True)
        else:
            st.info("No hay suficientes datos para calcular métricas del modelo.")
    else:
        st.info("Carga un modelo para ver las métricas de calidad.")

with tab_histogram:
    st.markdown("### Distribución de Tiempos de Vuelta")
    if not lap_summary.empty and "lap_time_s" in lap_summary.columns:
        if _PLOTLY_AVAILABLE and px is not None:
            # Histograma general
            fig_hist = px.histogram(
                lap_summary,
                x="lap_time_s",
                nbins=20,
                title="Histograma de Tiempos de Vuelta",
                labels={"lap_time_s": "Tiempo de Vuelta (s)"},
            )
            fig_hist.update_layout(showlegend=False)
            st.plotly_chart(fig_hist, use_container_width=True)

            # Estadísticas descriptivas
            st.markdown("### Estadísticas Descriptivas")
            stats = lap_summary["lap_time_s"].describe()
            stats_df = pd.DataFrame(
                {
                    "Estadística": stats.index,
                    "Valor": [round(float(val), 3) for val in stats.values],
                }
            )
            st.dataframe(stats_df, use_container_width=True)

            # Histograma por compuesto
            if "compound" in lap_summary.columns:
                st.markdown("### Por Compuesto")
                fig_hist_comp = px.histogram(
                    lap_summary,
                    x="lap_time_s",
                    color="compound",
                    nbins=15,
                    title="Distribución por Compuesto",
                    labels={"lap_time_s": "Tiempo de Vuelta (s)"},
                    opacity=0.7,
                )
                st.plotly_chart(fig_hist_comp, use_container_width=True)
        else:
            st.info("Plotly no disponible para histogramas.")
    else:
        st.info("No hay datos de tiempos de vuelta disponibles.")

with tab_consistency:
    st.markdown("### Análisis de Consistencia")
    consistency_metrics = calculate_consistency_metrics(lap_summary)
    if consistency_metrics:
        # Tabla de consistencia
        consistency_df = pd.DataFrame.from_dict(consistency_metrics, orient="index")
        consistency_df = consistency_df.round(4)
        consistency_df.columns = [
            "Desv. Estándar (s)",
            "Media (s)",
            "CV (%)",
            "Muestras",
        ]
        st.dataframe(consistency_df, use_container_width=True)

        # Interpretación
        st.markdown("**Interpretación:**")
        st.markdown(
            "- **Desv. Estándar**: Variabilidad en tiempos de vuelta (menor es mejor)"
        )
        st.markdown("- **CV (%)**: Coeficiente de variación (consistencia relativa)")
        st.markdown("- **Muestras**: Número de vueltas analizadas")

        # Gráfico de consistencia
        if _PLOTLY_AVAILABLE and go is not None:
            fig_consistency = go.Figure()

            compounds = list(consistency_metrics.keys())
            cv_values = [consistency_metrics[c]["cv_percent"] for c in compounds]

            fig_consistency.add_trace(
                go.Bar(
                    x=compounds,
                    y=cv_values,
                    marker_color="lightblue",
                    name="Coeficiente de Variación",
                )
            )

            fig_consistency.update_layout(
                title="Consistencia por Compuesto (Coeficiente de Variación %)",
                xaxis_title="Compuesto",
                yaxis_title="CV (%)",
                showlegend=False,
            )

            # Línea de referencia para buena consistencia (< 2%)
            fig_consistency.add_hline(
                y=2,
                line_dash="dash",
                line_color="red",
                annotation_text="Buena consistencia (< 2%)",
            )

            st.plotly_chart(fig_consistency, use_container_width=True)
    else:
        st.info(
            "No hay suficientes datos para analizar consistencia (mínimo 3 vueltas por compuesto)."
        )

with tab_compounds:
    st.markdown("### Comparación de Compuestos")
    if not lap_summary.empty and "compound" in lap_summary.columns:
        # Estadísticas por compuesto
        compound_stats = (
            lap_summary.groupby("compound")
            .agg({"lap_time_s": ["count", "mean", "std", "min", "max"]})
            .round(3)
        )

        # Aplanar columnas
        compound_stats.columns = [
            "_".join(col).strip() for col in compound_stats.columns
        ]
        compound_stats = compound_stats.rename(
            columns={
                "lap_time_s_count": "Vueltas",
                "lap_time_s_mean": "Media (s)",
                "lap_time_s_std": "Desv. Est. (s)",
                "lap_time_s_min": "Mejor (s)",
                "lap_time_s_max": "Peor (s)",
            }
        )

        st.dataframe(compound_stats, use_container_width=True)

        # Gráfico comparativo
        if _PLOTLY_AVAILABLE and px is not None:
            fig_comp = px.box(
                lap_summary,
                x="compound",
                y="lap_time_s",
                title="Distribución de Tiempos por Compuesto",
                labels={"lap_time_s": "Tiempo de Vuelta (s)", "compound": "Compuesto"},
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # Gráfico de evolución promedio
            if "tire_age" in lap_summary.columns:
                avg_by_age = (
                    lap_summary.groupby(["compound", "tire_age"])["lap_time_s"]
                    .mean()
                    .reset_index()
                )

                fig_evol = px.line(
                    avg_by_age,
                    x="tire_age",
                    y="lap_time_s",
                    color="compound",
                    markers=True,
                    title="Degradación Promedio por Compuesto",
                    labels={
                        "tire_age": "Edad del Neumático",
                        "lap_time_s": "Tiempo Promedio (s)",
                        "compound": "Compuesto",
                    },
                )
                st.plotly_chart(fig_evol, use_container_width=True)
        else:
            st.info("Plotly no disponible para gráficos comparativos.")
    else:
        st.info("No hay datos de compuestos disponibles para comparación.")

# Nueva pestaña: Condiciones Especiales (Safety Car y Lluvia)
with tab_conditions:
    st.markdown("### 🚨 Análisis de Condiciones Especiales")
    st.markdown(
        "Análisis del impacto de Safety Car y condiciones de lluvia en el rendimiento."
    )

    if not lap_summary.empty:
        # Análisis de Safety Car
        if COL_SAFETY_CAR in lap_summary.columns:
            safety_car_laps = lap_summary[lap_summary[COL_SAFETY_CAR]]
            if not safety_car_laps.empty:
                st.markdown(f"**🟡 Vueltas con Safety Car:** {len(safety_car_laps)}")
                avg_sc_time = safety_car_laps["lap_time_s"].mean()
                st.markdown(".2f")

                # Comparación con vueltas normales
                normal_laps = lap_summary[~lap_summary[COL_SAFETY_CAR]]
                if not normal_laps.empty:
                    avg_normal_time = normal_laps["lap_time_s"].mean()
                    slowdown = ((avg_sc_time / avg_normal_time) - 1) * 100
                    st.markdown(".1f")
            else:
                st.info("No se detectaron vueltas con Safety Car en los datos.")
        else:
            st.warning("Los datos no incluyen información de Safety Car.")

        st.markdown("---")

        # Análisis de lluvia
        if COL_RAIN in lap_summary.columns:
            rain_laps = lap_summary[lap_summary[COL_RAIN]]
            if not rain_laps.empty:
                st.markdown(f"**🌧️ Vueltas con lluvia:** {len(rain_laps)}")
                avg_rain_time = rain_laps["lap_time_s"].mean()
                st.markdown(".2f")

                # Comparación con vueltas secas
                dry_laps = lap_summary[~lap_summary[COL_RAIN]]
                if not dry_laps.empty:
                    avg_dry_time = dry_laps["lap_time_s"].mean()
                    slowdown = ((avg_rain_time / avg_dry_time) - 1) * 100
                    st.markdown(".1f")
            else:
                st.info("No se detectaron vueltas con lluvia en los datos.")
        else:
            st.warning("Los datos no incluyen información de lluvia.")

        # Simulador de impacto
        st.markdown("---")
        st.markdown("### 🎯 Simulador de Impacto en Estrategia")

        col1, col2 = st.columns(2)
        with col1:
            sc_percentage = st.slider(
                "Porcentaje de vueltas con Safety Car", 0, 50, 0, key="sc_slider"
            )
        with col2:
            rain_percentage = st.slider(
                "Porcentaje de vueltas con lluvia", 0, 50, 0, key="rain_slider"
            )

        if models and sc_percentage > 0 or rain_percentage > 0:
            st.markdown("**Impacto estimado en estrategia de carrera:**")

            # Mostrar impacto en tiempos de diferentes compuestos
            impact_data = []
            for compound, coeffs in models.items():
                base_time = coeffs[0]  # intercept
                sc_adjusted = adjust_lap_time_for_conditions(base_time, safety_car=True)
                rain_adjusted = adjust_lap_time_for_conditions(base_time, rain=True)

                impact_data.append(
                    {
                        "Compuesto": compound,
                        "Tiempo Base (s)": round(base_time, 2),
                        "Con Safety Car (s)": round(sc_adjusted, 2),
                        "Con Lluvia (s)": round(rain_adjusted, 2),
                    }
                )

            impact_df = pd.DataFrame(impact_data)
            st.dataframe(impact_df, use_container_width=True)

            st.info(
                "💡 Los modelos de degradación se ajustan automáticamente filtrando datos con condiciones especiales para mayor precisión."
            )
    else:
        st.info(
            "No hay datos de práctica disponibles para análisis de condiciones especiales."
        )

st.sidebar.markdown("---")
st.sidebar.caption(
    "Versión inicial. Mejora sugerida: simulador de degradación y comparación de estrategias alternativas."
)
