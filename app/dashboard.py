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
from _data import load_and_process
from _imports import (
    _PLOTLY_AVAILABLE,
    COL_LAP,
    DIR_MODELS,
    go,
    px,
)
from _tab_analysis import (
    render_compounds_tab,
    render_consistency_tab,
    render_histogram_tab,
    render_metrics_tab,
)
from _tab_conditions import render_conditions_tab
from _tab_strategy import render_strategy_tab

st.set_page_config(page_title="Estrategia Pit Stop F1 Manager 2024", layout="wide")

APP_VERSION = "1.2.0"


def _join_str(items: Iterable[object], sep: str = ", ") -> str:
    return sep.join(str(x) for x in items)


# --- Guardas de sesión para evitar re-ejecuciones en cascada ---
if "init_done" not in st.session_state:
    st.session_state["init_done"] = True
if "auto_guard" not in st.session_state:
    st.session_state["auto_guard"] = False

st.title("Dashboard Estrategia de Paradas — F1 Manager 2024")
st.caption(
    "Análisis de telemetría, stints, temperaturas y cumplimiento normativo FIA (simplificado)"
)
st.sidebar.markdown(f"**Versión:** {APP_VERSION}")

BASE_DIR = Path(__file__).resolve().parent
_candidate_paths = [
    Path("logs_in/exported_data"),
    BASE_DIR / "logs_in" / "exported_data",
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

assert DATA_ROOT is not None

MODELS_ROOT = BASE_DIR / DIR_MODELS

# ---------- sidebar selectors ----------
tracks = sorted({p.name for p in DATA_ROOT.iterdir() if p.is_dir()})
track: str = st.sidebar.selectbox("Circuito", tracks)
st.sidebar.caption("Origen datos: F1 Manager 2024 (adapter)")

session_root = DATA_ROOT / track
sessions = [p.name for p in session_root.iterdir() if p.is_dir()]
session: str = st.sidebar.selectbox("Sesión", sorted(sessions))

driver_root = session_root / session
drivers = []
for d in driver_root.rglob("*"):
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
csv_path = driver_dir / selected_csv

file_mtime = csv_path.stat().st_mtime

col_refresh_a, col_refresh_b, _ = st.sidebar.columns([1, 1, 1])
do_refresh = col_refresh_a.button("Refrescar")
auto_refresh = col_refresh_b.checkbox("Auto", value=False, help="Auto-refrescar cada 15s")
if do_refresh:
    st.cache_data.clear()
    st.rerun()

_run_every = 15 if auto_refresh else None

@st.fragment(run_every=_run_every)
def _auto_reloader():
    pass

_auto_reloader()

df, lap_summary, stints, compliance = load_and_process(csv_path, file_mtime)
st.sidebar.caption(
    f"Modificado: {datetime.fromtimestamp(file_mtime).strftime('%H:%M:%S')}"
)

# ---------- header metrics ----------
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
    st.dataframe(lap_summary, width='stretch', height=300)

st.subheader("Stints")
if stints:
    stint_df = pd.DataFrame([s.__dict__ for s in stints])
    st.dataframe(stint_df, width='stretch')
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
notes_val = compliance.get("notes")
if notes_val:
    if isinstance(notes_val, (list, tuple, set)):
        st.warning(_join_str([str(n) for n in notes_val], sep="\n"))
    elif isinstance(notes_val, str):
        st.warning(notes_val)
    else:
        st.warning(str(notes_val))
st.caption(
    "Reglas simplificadas con fines analíticos; para validación oficial consultar reglamento FIA completo."
)

# models se actualiza desde render_strategy_tab y se pasa a tabs de análisis/condiciones
models: dict = {}

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
            st.plotly_chart(fig, width='stretch')
    else:
        st.info("No hay datos de tiempos de vuelta.")

with tab_ttemps:
    temp_col_names = ["flTemp", "frTemp", "rlTemp", "rrTemp"]
    existing = [c for c in temp_col_names if c in df.columns]
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
        st.plotly_chart(fig2, width='stretch')
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
            st.plotly_chart(fig3, width='stretch')
    else:
        st.info("No hay datos de temperatura de pista/aire.")

with tab_evol:
    if _PLOTLY_AVAILABLE and px is not None and not lap_summary.empty:
        fig4 = create_compound_evolution_chart(lap_summary)
        if fig4 is not None:
            st.plotly_chart(fig4, width='stretch')
    else:
        st.info("Sin datos para mostrar evolución de compuesto.")

with tab_strategy:
    models = render_strategy_tab(
        track, session, driver, lap_summary, DATA_ROOT, MODELS_ROOT, APP_VERSION
    )

with tab_wear:
    wear_cols = ["flDeg", "frDeg", "rlDeg", "rrDeg"]
    have_wear = [c for c in wear_cols if c in df.columns]
    if not have_wear:
        st.info("No hay columnas de desgaste (flDeg, frDeg, rlDeg, rrDeg).")
    elif _PLOTLY_AVAILABLE and px is not None:
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
        st.plotly_chart(figw, width='stretch')
        if not lap_summary.empty:
            last_per_lap = df.sort_values("timestamp").groupby(COL_LAP).tail(1)
            cols_present = [c for c in wear_cols if c in last_per_lap.columns]
            st.dataframe(
                last_per_lap[[COL_LAP] + cols_present],
                width='stretch',
                height=300,
            )
    else:
        st.info("Plotly no disponible para graficar desgaste.")

with tab_metrics:
    render_metrics_tab(lap_summary, models)

with tab_histogram:
    render_histogram_tab(lap_summary)

with tab_consistency:
    render_consistency_tab(lap_summary)

with tab_compounds:
    render_compounds_tab(lap_summary)

with tab_conditions:
    render_conditions_tab(lap_summary, models)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Versión inicial. Mejora sugerida: simulador de degradación y comparación de estrategias alternativas."
)

