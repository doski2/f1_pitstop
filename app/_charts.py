"""Cached chart-creation functions (Plotly)."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from _imports import (
    _PLOTLY_AVAILABLE,
    COL_COMPOUND,
    COL_LAP,
    COL_LAP_TIME,
    COL_TIRE_AGE,
    COMPOUND_COLOR_MAP,
    compound_color,
    display_compound,
    go,
    px,
)


def _fmt_laptime(secs: float) -> str:
    """Convierte segundos a formato m:ss.sss (ej. 97.392 -> '1:37.392')."""
    if secs is None or (isinstance(secs, float) and pd.isna(secs)):
        return ""
    m = int(secs) // 60
    s = secs - m * 60
    return f"{m}:{s:06.3f}"


@st.cache_data(show_spinner=False)
def create_lap_times_chart(lap_summary: pd.DataFrame):
    """Crea gráfico de tiempos por vuelta con caché."""
    if (
        not _PLOTLY_AVAILABLE
        or px is None
        or lap_summary.empty
        or "lap_time_s" not in lap_summary
    ):
        return None

    plot_df = lap_summary.copy()
    plot_df["_lap_time_fmt"] = plot_df[COL_LAP_TIME].apply(_fmt_laptime)
    plot_df["_compound_label"] = plot_df[COL_COMPOUND].apply(display_compound)

    color_map = {
        display_compound(c): COMPOUND_COLOR_MAP.get(
            display_compound(c), COMPOUND_COLOR_MAP.get(c, "#888888")
        )
        for c in plot_df[COL_COMPOUND].dropna().unique()
    }

    fig = px.line(
        plot_df,
        x=COL_LAP,
        y=COL_LAP_TIME,
        color="_compound_label",
        markers=True,
        custom_data=["_lap_time_fmt"],
        color_discrete_map=color_map,
        labels={
            COL_LAP: "Vuelta",
            COL_LAP_TIME: "Tiempo",
            "_compound_label": "Compuesto",
        },
        title="Tiempos de Vuelta",
    )

    # Eje Y con formato m:ss
    t_vals = plot_df[COL_LAP_TIME].dropna()
    if not t_vals.empty:
        t_min, t_max = t_vals.min(), t_vals.max()
        step = 5  # ticks cada 5 s
        tick_vals = list(range(int(t_min // step) * step, int(t_max) + step + 1, step))
        tick_text = [_fmt_laptime(float(v)) for v in tick_vals]
        fig.update_yaxes(tickvals=tick_vals, ticktext=tick_text)

    # Hover con formato m:ss.sss
    fig.update_traces(
        hovertemplate="Vuelta %{x}  —  %{customdata[0]}<extra>%{fullData.name}</extra>"
    )

    if go is not None and "pit_stop" in plot_df.columns:
        # Paradas con cambio de neumáticos (triángulo rojo)
        tire_col = "tire_change_pit" if "tire_change_pit" in plot_df.columns else "pit_stop"
        tire_pts = plot_df[plot_df[tire_col].fillna(False)]
        if not tire_pts.empty:
            fig.add_trace(
                go.Scatter(
                    x=tire_pts[COL_LAP],
                    y=tire_pts[COL_LAP_TIME],
                    customdata=list(zip(tire_pts["_lap_time_fmt"])),
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=12, color="#E8002D"),
                    name="Pit (cambio ruedas)",
                    hovertemplate="Pit cambio — Vuelta %{x}  —  %{customdata[0]}<extra></extra>",
                )
            )
        # Paradas sin cambio de neumáticos (triángulo gris)
        if "tire_change_pit" in plot_df.columns:
            no_tire_pts = plot_df[
                plot_df["pit_stop"].fillna(False) & ~plot_df["tire_change_pit"].fillna(False)
            ]
            if not no_tire_pts.empty:
                fig.add_trace(
                    go.Scatter(
                        x=no_tire_pts[COL_LAP],
                        y=no_tire_pts[COL_LAP_TIME],
                        customdata=list(zip(no_tire_pts["_lap_time_fmt"])),
                        mode="markers",
                        marker=dict(symbol="triangle-down", size=12, color="#888888"),
                        name="Pit (sin cambio ruedas)",
                        hovertemplate="Pit sin cambio — Vuelta %{x}  —  %{customdata[0]}<extra></extra>",
                    )
                )

    return fig


@st.cache_data(show_spinner=False)
def create_degradation_chart(lap_summary: pd.DataFrame, models: dict):
    """Crea gráfico de degradación con caché."""
    if not _PLOTLY_AVAILABLE or go is None or lap_summary.empty:
        return None

    fig = go.Figure()

    for compound, params in models.items():
        compound_data = lap_summary[lap_summary["compound"] == compound]
        if not compound_data.empty and "tire_age" in compound_data.columns:
            intercept, slope = params[0], params[1]
            predictions = intercept + slope * compound_data["tire_age"]
            fmt_pred = predictions.apply(_fmt_laptime)
            clabel = display_compound(compound)
            ccolor = compound_color(compound)

            fig.add_trace(
                go.Scatter(
                    x=compound_data["tire_age"],
                    y=predictions,
                    customdata=list(zip(fmt_pred)),
                    mode="lines",
                    name=f"{clabel} (modelo)",
                    line=dict(dash="dash", color=ccolor),
                    hovertemplate="Edad %{x}  \u2014  %{customdata[0]}<extra>%{fullData.name}</extra>",
                )
            )

            fmt_real = compound_data["lap_time_s"].apply(_fmt_laptime)
            fig.add_trace(
                go.Scatter(
                    x=compound_data["tire_age"],
                    y=compound_data["lap_time_s"],
                    customdata=list(zip(fmt_real)),
                    mode="markers",
                    name=f"{clabel} (real)",
                    marker=dict(color=ccolor),
                    opacity=0.7,
                    hovertemplate="Edad %{x}  \u2014  %{customdata[0]}<extra>%{fullData.name}</extra>",
                )
            )

    # Eje Y con formato m:ss
    all_times = lap_summary["lap_time_s"].dropna()
    if not all_times.empty:
        t_min, t_max = all_times.min(), all_times.max()
        step = 5
        tick_vals = list(range(int(t_min // step) * step, int(t_max) + step + 1, step))
        tick_text = [_fmt_laptime(float(v)) for v in tick_vals]
        fig.update_yaxes(tickvals=tick_vals, ticktext=tick_text)

    fig.update_layout(
        title="Degradación de Neumáticos",
        xaxis_title="Edad del Neumático",
        yaxis_title="Tiempo de Vuelta",
        legend_title="Compuesto",
    )
    return fig


@st.cache_data(show_spinner=False)
def create_temperatures_chart(df: pd.DataFrame):
    """Crea gráfico de temperaturas con caché."""
    if (
        not _PLOTLY_AVAILABLE
        or go is None
        or df.empty
        or "trackTemp" not in df.columns
        or "airTemp" not in df.columns
    ):
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["trackTemp"], name="Pista"))
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["airTemp"], name="Aire"))

    if "flTemp" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["flTemp"], name="Delantero Izq")
        )
    if "frTemp" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["frTemp"], name="Delantero Der")
        )
    if "rlTemp" in df.columns:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["rlTemp"], name="Trasero Izq"))
    if "rrTemp" in df.columns:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["rrTemp"], name="Trasero Der"))

    fig.update_layout(
        title="Temperatura Pista vs Aire",
        xaxis_title="Tiempo",
        yaxis_title="°C (según juego)",
    )
    return fig


@st.cache_data(show_spinner=False)
def create_compound_evolution_chart(lap_summary: pd.DataFrame):
    """Crea gráfico de evolución de compuesto con caché."""
    if not _PLOTLY_AVAILABLE or px is None or lap_summary.empty:
        return None

    compound_evo_df = lap_summary.copy()
    compound_evo_df["_compound_label"] = compound_evo_df[COL_COMPOUND].apply(
        display_compound
    )
    evo_color_map = {
        display_compound(c): COMPOUND_COLOR_MAP.get(
            display_compound(c), COMPOUND_COLOR_MAP.get(c, "#888888")
        )
        for c in compound_evo_df[COL_COMPOUND].dropna().unique()
    }

    fig = px.scatter(
        compound_evo_df,
        x=COL_LAP,
        y=COL_TIRE_AGE,
        color="_compound_label",
        size=COL_LAP_TIME,
        color_discrete_map=evo_color_map,
        labels={
            COL_LAP: "Vuelta",
            COL_TIRE_AGE: "Edad Neumático (vueltas)",
            "_compound_label": "Compuesto",
        },
        title="Evolución Edad Neumático / Compuesto",
    )
    return fig
