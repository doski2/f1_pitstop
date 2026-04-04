"""Render functions for analysis tabs: Metrics, Histogram, Consistency, Compounds."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from _imports import _PLOTLY_AVAILABLE, COL_LAP, go, px
from _metrics import calculate_consistency_metrics, calculate_model_metrics


def render_metrics_tab(lap_summary: pd.DataFrame, models: dict) -> None:
    st.markdown("### Métricas de Calidad del Modelo")
    if not models:
        st.info("Carga un modelo para ver las métricas de calidad.")
        return

    model_metrics = calculate_model_metrics(lap_summary, models)
    if not model_metrics:
        st.info("No hay suficientes datos para calcular métricas del modelo.")
        return

    metrics_df = pd.DataFrame.from_dict(model_metrics, orient="index")
    metrics_df = metrics_df.round(4)
    metrics_df.columns = ["MAE (s)", "R²", "Muestras"]
    st.dataframe(metrics_df, width='stretch')

    st.markdown(
        "**Interpretación:**\n"
        "- **MAE**: Error absoluto medio en segundos (menor es mejor)\n"
        "- **R²**: Coeficiente de determinación (más cercano a 1.0 es mejor)\n"
        "- **Muestras**: Número de puntos de datos usados"
    )

    if not lap_summary.empty and _PLOTLY_AVAILABLE and go is not None:
        st.markdown("### Análisis de Residuos")
        fig_resid = go.Figure()
        for compound, params in models.items():
            if len(params) >= 2 and compound in lap_summary["compound"].values:
                compound_data = lap_summary[lap_summary["compound"] == compound]
                if not compound_data.empty and "tire_age" in compound_data.columns:
                    if len(params) == 4:
                        a, b_age, c_fuel, d_temp = params
                        fuel_s = compound_data["fuel"] if "fuel" in compound_data.columns else pd.Series(0.0, index=compound_data.index)
                        temp_s = compound_data["trackTemp"] if "trackTemp" in compound_data.columns else pd.Series(40.0, index=compound_data.index)
                        predictions = (
                            a
                            + b_age * compound_data["tire_age"]
                            + c_fuel * fuel_s.fillna(0.0)
                            + d_temp * temp_s.fillna(40.0)
                        )
                    elif len(params) == 3:
                        a, b_age, c_fuel = params
                        fuel_s = compound_data["fuel"] if "fuel" in compound_data.columns else pd.Series(0.0, index=compound_data.index)
                        predictions = a + b_age * compound_data["tire_age"] + c_fuel * fuel_s.fillna(0.0)
                    else:
                        predictions = params[0] + params[1] * compound_data["tire_age"]
                    residuals = compound_data["lap_time_s"] - predictions
                    fig_resid.add_trace(
                        go.Scatter(
                            x=compound_data["tire_age"],
                            y=residuals,
                            mode="markers",
                            name=f"{compound} residuos",
                            text=[
                                f"Vuelta {int(lap)}" for lap in compound_data[COL_LAP]
                            ],
                        )
                    )
        fig_resid.update_layout(
            title="Residuos del Modelo (Tiempo Real - Tiempo Predicho)",
            xaxis_title="Edad del Neumático",
            yaxis_title="Residuo (segundos)",
            showlegend=True,
        )
        st.plotly_chart(fig_resid, width='stretch')


def render_histogram_tab(lap_summary: pd.DataFrame) -> None:
    st.markdown("### Distribución de Tiempos de Vuelta")
    if lap_summary.empty or "lap_time_s" not in lap_summary.columns:
        st.info("No hay datos de tiempos de vuelta disponibles.")
        return

    if not _PLOTLY_AVAILABLE or px is None:
        st.info("Plotly no disponible para histogramas.")
        return

    fig_hist = px.histogram(
        lap_summary,
        x="lap_time_s",
        nbins=20,
        title="Histograma de Tiempos de Vuelta",
        labels={"lap_time_s": "Tiempo de Vuelta (s)"},
    )
    fig_hist.update_layout(showlegend=False)
    st.plotly_chart(fig_hist, width='stretch')

    st.markdown("### Estadísticas Descriptivas")
    stats = lap_summary["lap_time_s"].describe()
    stats_df = pd.DataFrame(
        {
            "Estadística": stats.index,
            "Valor": [round(float(val), 3) for val in stats.values],
        }
    )
    st.dataframe(stats_df, width='stretch')

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
        st.plotly_chart(fig_hist_comp, width='stretch')


def render_consistency_tab(lap_summary: pd.DataFrame) -> None:
    st.markdown("### Análisis de Consistencia")
    consistency_metrics = calculate_consistency_metrics(lap_summary)
    if not consistency_metrics:
        st.info(
            "No hay suficientes datos para analizar consistencia (mínimo 3 vueltas por compuesto)."
        )
        return

    consistency_df = pd.DataFrame.from_dict(consistency_metrics, orient="index")
    consistency_df = consistency_df.round(4)
    consistency_df.columns = ["Desv. Estándar (s)", "Media (s)", "CV (%)", "Muestras"]
    st.dataframe(consistency_df, width='stretch')

    st.markdown(
        "**Interpretación:**\n"
        "- **Desv. Estándar**: Variabilidad en tiempos de vuelta (menor es mejor)\n"
        "- **CV (%)**: Coeficiente de variación (consistencia relativa)\n"
        "- **Muestras**: Número de vueltas analizadas"
    )

    if not _PLOTLY_AVAILABLE or go is None:
        return

    compounds = list(consistency_metrics.keys())
    cv_values = [consistency_metrics[c]["cv_percent"] for c in compounds]

    fig_c = go.Figure()
    fig_c.add_trace(
        go.Bar(
            x=compounds,
            y=cv_values,
            marker_color="lightblue",
            name="Coeficiente de Variación",
        )
    )
    fig_c.update_layout(
        title="Consistencia por Compuesto (Coeficiente de Variación %)",
        xaxis_title="Compuesto",
        yaxis_title="CV (%)",
        showlegend=False,
    )
    fig_c.add_hline(
        y=2,
        line_dash="dash",
        line_color="red",
        annotation_text="Buena consistencia (< 2%)",
    )
    st.plotly_chart(fig_c, width='stretch')


def render_compounds_tab(lap_summary: pd.DataFrame) -> None:
    st.markdown("### Comparación de Compuestos")
    if lap_summary.empty or "compound" not in lap_summary.columns:
        st.info("No hay datos de compuestos disponibles para comparación.")
        return

    compound_stats = (
        lap_summary.groupby("compound")
        .agg({"lap_time_s": ["count", "mean", "std", "min", "max"]})
        .round(3)
    )
    compound_stats.columns = ["_".join(col).strip() for col in compound_stats.columns]
    compound_stats = compound_stats.rename(
        columns={
            "lap_time_s_count": "Vueltas",
            "lap_time_s_mean": "Media (s)",
            "lap_time_s_std": "Desv. Est. (s)",
            "lap_time_s_min": "Mejor (s)",
            "lap_time_s_max": "Peor (s)",
        }
    )
    st.dataframe(compound_stats, width='stretch')

    if not _PLOTLY_AVAILABLE or px is None:
        st.info("Plotly no disponible para gráficos comparativos.")
        return

    fig_comp = px.box(
        lap_summary,
        x="compound",
        y="lap_time_s",
        title="Distribución de Tiempos por Compuesto",
        labels={"lap_time_s": "Tiempo de Vuelta (s)", "compound": "Compuesto"},
    )
    st.plotly_chart(fig_comp, width='stretch')

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
        st.plotly_chart(fig_evol, width='stretch')
