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

    fig = px.line(
        plot_df,
        x=COL_LAP,
        y=COL_LAP_TIME,
        color=COL_COMPOUND,
        markers=True,
        custom_data=["_lap_time_fmt"],
        labels={
            COL_LAP: "Vuelta",
            COL_LAP_TIME: "Tiempo",
            COL_COMPOUND: "Compuesto",
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

    if (
        "pit_stop" in plot_df.columns
        and plot_df["pit_stop"].any()
        and go is not None
    ):
        pit_pts = plot_df[plot_df["pit_stop"]]
        fig.add_trace(
            go.Scatter(
                x=pit_pts[COL_LAP],
                y=pit_pts[COL_LAP_TIME],
                customdata=list(zip(pit_pts["_lap_time_fmt"])),
                mode="markers",
                marker=dict(symbol="triangle-down", size=12, color="red"),
                name="Pit Stop",
                hovertemplate="Pit Stop — Vuelta %{x}  —  %{customdata[0]}<extra></extra>",
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

            fig.add_trace(
                go.Scatter(
                    x=compound_data["tire_age"],
                    y=predictions,
                    customdata=list(zip(fmt_pred)),
                    mode="lines",
                    name=f"{compound} (modelo)",
                    line=dict(dash="dash"),
                    hovertemplate="Edad %{x}  —  %{customdata[0]}<extra>%{fullData.name}</extra>",
                )
            )

            fmt_real = compound_data["lap_time_s"].apply(_fmt_laptime)
            fig.add_trace(
                go.Scatter(
                    x=compound_data["tire_age"],
                    y=compound_data["lap_time_s"],
                    customdata=list(zip(fmt_real)),
                    mode="markers",
                    name=f"{compound} (real)",
                    opacity=0.7,
                    hovertemplate="Edad %{x}  —  %{customdata[0]}<extra>%{fullData.name}</extra>",
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

    fig = px.scatter(
        lap_summary,
        x=COL_LAP,
        y=COL_TIRE_AGE,
        color=COL_COMPOUND,
        size=COL_LAP_TIME,
        labels={COL_LAP: "Vuelta", COL_TIRE_AGE: "Edad Neumático (vueltas)"},
        title="Evolución Edad Neumático / Compuesto",
    )
    return fig
