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

    fig = px.line(
        lap_summary,
        x=COL_LAP,
        y=COL_LAP_TIME,
        color=COL_COMPOUND,
        markers=True,
        labels={
            COL_LAP: "Vuelta",
            COL_LAP_TIME: "Tiempo (s)",
            COL_COMPOUND: "Compuesto",
        },
        title="Tiempos de Vuelta",
    )

    if (
        "pit_stop" in lap_summary.columns
        and lap_summary["pit_stop"].any()
        and go is not None
    ):
        pit_pts = lap_summary[lap_summary["pit_stop"]]
        fig.add_trace(
            go.Scatter(
                x=pit_pts[COL_LAP],
                y=pit_pts[COL_LAP_TIME],
                mode="markers",
                marker=dict(symbol="triangle-down", size=12, color="red"),
                name="Pit Stop",
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

            fig.add_trace(
                go.Scatter(
                    x=compound_data["tire_age"],
                    y=predictions,
                    mode="lines",
                    name=f"{compound} (modelo)",
                    line=dict(dash="dash"),
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=compound_data["tire_age"],
                    y=compound_data["lap_time_s"],
                    mode="markers",
                    name=f"{compound} (real)",
                    opacity=0.7,
                )
            )

    fig.update_layout(
        title="Degradación de Neumáticos",
        xaxis_title="Edad del Neumático",
        yaxis_title="Tiempo de Vuelta (s)",
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
