"""Dashboard principal de estrategia.

Nota sobre imports: si ejecutas `streamlit run dashboard.py` dentro de la carpeta `app/`,
Python no verá el paquete hermano `adapters/` en el nivel raíz y fallará con
`ModuleNotFoundError: No module named 'adapters'`.

Solución: insertar el directorio raíz del proyecto en `sys.path` antes de importar.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.express as px  # type: ignore
    import plotly.graph_objects as go  # type: ignore

    _PLOTLY_AVAILABLE = True
except ImportError:
    px = None  # type: ignore
    go = None  # type: ignore
    _PLOTLY_AVAILABLE = False
# Inserta raíz del repo (padre de app/) para que 'adapters' sea importable aun ejecutando dentro de app/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Imports del proyecto (después de asegurar sys.path)
from strategy import (  # noqa: E402
    build_lap_summary,
    build_stints,
    detect_pit_events,
    fia_compliance_check,
)
from strategy_model import (  # noqa: E402
    collect_practice_data,
    enumerate_plans,
    fit_degradation_model,
    live_pit_recommendation,
)

from adapters.f1manager2024 import load_raw_csv  # noqa: E402

# TODO: fuel-aware modeling integration in subsequent iteration


st.set_page_config(page_title="Estrategia Pit Stop F1 Manager 2024", layout="wide")

APP_VERSION = "1.0.2"
st.title("Dashboard Estrategia de Paradas – F1 Manager 2024")
st.caption(
    "Análisis de telemetría, stints, temperaturas y cumplimiento normativo FIA (simplificado)"
)
st.sidebar.markdown(f"**Versión:** {APP_VERSION}")

BASE_DIR = _ROOT  # raíz del proyecto (más robusto para streamlit run)
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
        "No se encontró la carpeta de datos en rutas intentadas: "
        + "\n".join(str(p.resolve()) for p in _candidate_paths)
    )
    st.stop()

MODELS_ROOT = BASE_DIR / "models"


def load_precomputed_model(track: str, driver: str):
    path = MODELS_ROOT / track / f"{driver}_model.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("models", {})
            models = {}
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
        except Exception as e:  # noqa
            st.warning(f"Error cargando modelo precomputado: {e}")
    return {}, {}


def save_model_json(
    track: str, driver: str, models: dict, sessions_used: list, fuel_used: bool
):
    MODELS_ROOT.mkdir(parents=True, exist_ok=True)
    out_dir = MODELS_ROOT / track
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "track": track,
            "driver": driver,
            "sessions_included": sessions_used,
            "fuel_used": fuel_used,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        },
        "models": {k: list(v) for k, v in models.items()},
    }
    out_path = out_dir / f"{driver}_model.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    st.success(f"Modelo guardado en {out_path}")


# Selección jerárquica: Circuito -> Sesión -> Piloto -> Archivo
tracks = sorted({p.name for p in DATA_ROOT.iterdir() if p.is_dir()})
track = st.sidebar.selectbox("Circuito", tracks)
st.sidebar.caption("Origen datos: F1 Manager 2024 (adapter)")

session_root = DATA_ROOT / track
sessions = [p.name for p in session_root.iterdir() if p.is_dir()]
session = st.sidebar.selectbox("Sesión", sorted(sessions))

driver_root = session_root / session
drivers = []
for d in driver_root.rglob("*"):  # allow deeper structure (driver folders)
    if d.is_dir() and any(f.suffix == ".csv" for f in d.glob("*.csv")):
        drivers.append(d.name)
drivers = sorted(set(drivers))
driver = st.sidebar.selectbox("Piloto", drivers) if drivers else None

if not driver:
    st.warning("Seleccione un piloto con datos.")
    st.stop()

driver_dir = driver_root / driver  # type: ignore[arg-type]
csv_files = sorted(driver_dir.glob("*.csv"))
if not csv_files:
    st.warning("No hay archivos CSV para este piloto.")
    st.stop()

selected_csv = st.sidebar.selectbox("Archivo Telemetría", [f.name for f in csv_files])
csv_path = driver_dir / selected_csv


@st.cache_data(show_spinner=True)
def load_and_process(path: Path, mtime: float):
    """Carga y procesa un archivo de telemetría vía adapter F1 Manager 2024.
    mtime se incluye para invalidar cache cuando el archivo cambia.
    """
    df = load_raw_csv(path)
    df = detect_pit_events(df)
    lap_summary = build_lap_summary(df)
    stints = build_stints(lap_summary)
    compliance = fia_compliance_check(stints, df.get("weather"))
    return df, lap_summary, stints, compliance


file_mtime = csv_path.stat().st_mtime

col_refresh_a, col_refresh_b, col_refresh_c = st.sidebar.columns([1, 1, 1])
do_refresh = col_refresh_a.button("Refrescar")
auto_refresh = col_refresh_b.checkbox(
    "Auto", value=False, help="Auto-refrescar cada 15s"
)
if auto_refresh:
    _autoref = getattr(st, "autorefresh", None)
    if callable(_autoref):
        _autoref(interval=15000, key="auto_rfr")  # type: ignore
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
        int(lap_summary["currentLap"].max() if not lap_summary.empty else 0),
    )
with col_meta2:
    unique_compounds = (
        ", ".join(sorted(lap_summary["compound"].dropna().unique()))
        if "compound" in lap_summary
        else "—"
    )
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
if compliance["notes"]:
    st.warning("\n".join(compliance["notes"]))
st.caption(
    "Reglas simplificadas con fines analíticos; para validación oficial consultar reglamento FIA completo."
)

st.subheader("Gráficos")
if not _PLOTLY_AVAILABLE:
    st.warning(
        "Plotly no está instalado. Instale dependencias: `pip install -r requirements.txt`."
    )
    st.stop()
tab_lap, tab_ttemps, tab_trackair, tab_evol, tab_strategy, tab_wear = st.tabs(
    [
        "Lap Times",
        "Tº Neumáticos",
        "Tº Pista/Aire",
        "Evolución Compuesto",
        "Estrategia",
        "Desgaste",
    ]
)

with tab_lap:
    if (
        _PLOTLY_AVAILABLE
        and px is not None
        and not lap_summary.empty
        and "lap_time_s" in lap_summary
    ):
        fig = px.line(
            lap_summary,
            x="currentLap",
            y="lap_time_s",
            color="compound",
            markers=True,
            labels={
                "currentLap": "Vuelta",
                "lap_time_s": "Tiempo (s)",
                "compound": "Compuesto",
            },
            title="Tiempos de Vuelta",
        )
        # Añadir marcadores de pit stop
        if (
            "pit_stop" in lap_summary.columns
            and lap_summary["pit_stop"].any()
            and go is not None
        ):
            pit_pts = lap_summary[lap_summary["pit_stop"]]
            fig.add_trace(
                go.Scatter(
                    x=pit_pts["currentLap"],
                    y=pit_pts["lap_time_s"],
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=12, color="red"),
                    name="Pit Stop",
                )
            )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de tiempos de vuelta.")

with tab_ttemps:
    temp_cols = ["flTemp", "frTemp", "rlTemp", "rrTemp"]
    existing = [c for c in temp_cols if c in df.columns]
    if _PLOTLY_AVAILABLE and px is not None and existing:
        melt = df.melt(
            id_vars=["timestamp", "currentLap"],
            value_vars=existing,
            var_name="Rueda",
            value_name="Temp",
        )
        fig2 = px.line(
            melt,
            x="timestamp",
            y="Temp",
            color="Rueda",
            hover_data=["currentLap"],
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
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df["timestamp"], y=df["trackTemp"], name="Pista"))
        fig3.add_trace(go.Scatter(x=df["timestamp"], y=df["airTemp"], name="Aire"))
        fig3.update_layout(
            title="Temperatura Pista vs Aire",
            xaxis_title="Tiempo",
            yaxis_title="°C (según juego)",
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No hay datos de temperatura de pista/aire.")

with tab_evol:
    if _PLOTLY_AVAILABLE and px is not None and not lap_summary.empty:
        fig4 = px.scatter(
            lap_summary,
            x="currentLap",
            y="tire_age",
            color="compound",
            size="lap_time_s",
            labels={"currentLap": "Vuelta", "tire_age": "Edad Neumático (vueltas)"},
            title="Evolución Edad Neumático / Compuesto",
        )
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Sin datos para mostrar evolución de compuesto.")

with tab_strategy:
    st.markdown("### Planificación de Estrategia (Combustible y Degradación)")
    is_race = "race" in session.lower()
    assert driver is not None
    practice_data = collect_practice_data(DATA_ROOT, track, driver)
    fallback_used = False
    if practice_data.empty and is_race and not lap_summary.empty:
        if st.checkbox(
            "Sin prácticas. Usar vueltas iniciales de carrera como estimación provisoria"
        ):
            initial = lap_summary[lap_summary["lap_time_s"].notna()].nsmallest(
                12, "currentLap"
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
                diffs = (-fuel_series.diff()).dropna()
                diffs = pd.to_numeric(diffs, errors="coerce").dropna()
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
        pre_models = {}
        pre_meta = {}
        if use_pre:
            pre_models, pre_meta = load_precomputed_model(track, driver)
            if pre_models:
                st.caption(
                    f"Modelo precomputado cargado (fuel_used={pre_meta.get('fuel_used')})"
                )
        if pre_models:
            models = pre_models
        else:
            models = fit_degradation_model(practice_data)
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
                    a, b_age = coeffs  # type: ignore
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
                save_model_json(track, driver, models, sessions_used, fuel_used)
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
                int(lap_summary["currentLap"].max()) if not lap_summary.empty else 0
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
                plans = enumerate_plans(
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
                current_lap = int(lap_summary["currentLap"].max())
                last_row = lap_summary[lap_summary["currentLap"] == current_lap].tail(1)
                comp_now = last_row["compound"].iloc[0] if not last_row.empty else None
                age_now = int(last_row["tire_age"].iloc[0]) if not last_row.empty else 0
                current_fuel = (
                    float(last_row["fuel"].iloc[0])
                    if use_fuel and "fuel" in last_row.columns and not last_row.empty
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

with tab_wear:
    wear_cols = ["flDeg", "frDeg", "rlDeg", "rrDeg"]
    have_wear = [c for c in wear_cols if c in df.columns]
    if not have_wear:
        st.info("No hay columnas de desgaste (flDeg, frDeg, rlDeg, rrDeg).")
    else:
        if _PLOTLY_AVAILABLE and px is not None:
            wear_melt = df.melt(
                id_vars=["timestamp", "currentLap"],
                value_vars=have_wear,
                var_name="Rueda",
                value_name="Desgaste",
            )
            figw = px.line(
                wear_melt,
                x="currentLap",
                y="Desgaste",
                color="Rueda",
                title="Desgaste Neumáticos (%)",
                markers=True,
            )
            st.plotly_chart(figw, use_container_width=True)
            # Resumen por vuelta (última muestra de cada vuelta)
            if not lap_summary.empty:
                last_per_lap = df.sort_values("timestamp").groupby("currentLap").tail(1)
                cols_present = [c for c in wear_cols if c in last_per_lap.columns]
                st.dataframe(
                    last_per_lap[["currentLap"] + cols_present],
                    use_container_width=True,
                    height=300,
                )
        else:
            st.info("Plotly no disponible para graficar desgaste.")

st.sidebar.markdown("---")
st.sidebar.caption(
    "Versión inicial. Mejora sugerida: simulador de degradación y comparación de estrategias alternativas."
)
