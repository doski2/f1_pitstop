"""Render function for the Condiciones Especiales tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from _imports import (
    COL_RAIN,
    COL_SAFETY_CAR,
    adjust_lap_time_for_conditions,
)


def render_conditions_tab(lap_summary: pd.DataFrame, models: dict) -> None:
    st.markdown("### 🚨 Análisis de Condiciones Especiales")
    st.markdown(
        "Análisis del impacto de Safety Car y condiciones de lluvia en el rendimiento."
    )

    if lap_summary.empty:
        st.info(
            "No hay datos de práctica disponibles para análisis de condiciones especiales."
        )
        return

    # ── Safety Car ───────────────────────────────────────────────────────────
    if COL_SAFETY_CAR in lap_summary.columns:
        safety_car_laps = lap_summary[lap_summary[COL_SAFETY_CAR]]
        if not safety_car_laps.empty:
            st.markdown(f"**🟡 Vueltas con Safety Car:** {len(safety_car_laps)}")
            avg_sc_time = safety_car_laps["lap_time_s"].mean()
            st.markdown(f"**Tiempo promedio SC:** {avg_sc_time:.2f}s")
            normal_laps = lap_summary[~lap_summary[COL_SAFETY_CAR]]
            if not normal_laps.empty:
                avg_normal_time = normal_laps["lap_time_s"].mean()
                slowdown = ((avg_sc_time / avg_normal_time) - 1) * 100
                st.markdown(f"**Enlentecimiento respecto normales:** +{slowdown:.1f}%")
        else:
            st.info("No se detectaron vueltas con Safety Car en los datos.")
    else:
        st.warning("Los datos no incluyen información de Safety Car.")

    st.markdown("---")

    # ── Lluvia ────────────────────────────────────────────────────────────────
    if COL_RAIN in lap_summary.columns:
        rain_laps = lap_summary[lap_summary[COL_RAIN]]
        if not rain_laps.empty:
            st.markdown(f"**🌧️ Vueltas con lluvia:** {len(rain_laps)}")
            avg_rain_time = rain_laps["lap_time_s"].mean()
            st.markdown(f"**Tiempo promedio lluvia:** {avg_rain_time:.2f}s")
            dry_laps = lap_summary[~lap_summary[COL_RAIN]]
            if not dry_laps.empty:
                avg_dry_time = dry_laps["lap_time_s"].mean()
                slowdown = ((avg_rain_time / avg_dry_time) - 1) * 100
                st.markdown(f"**Enlentecimiento respecto vueltas secas:** +{slowdown:.1f}%")
        else:
            st.info("No se detectaron vueltas con lluvia en los datos.")
    else:
        st.warning("Los datos no incluyen información de lluvia.")

    st.markdown("---")

    # ── Simulador de impacto ──────────────────────────────────────────────────
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

    if models and (sc_percentage > 0 or rain_percentage > 0):
        st.markdown("**Impacto estimado en estrategia de carrera:**")
        impact_data = []
        for compound, coeffs in models.items():
            base_time = coeffs[0]
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
        st.dataframe(pd.DataFrame(impact_data), use_container_width=True)
        st.info(
            "💡 Los modelos de degradación se ajustan automáticamente filtrando datos "
            "con condiciones especiales para mayor precisión."
        )
