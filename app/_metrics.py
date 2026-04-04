"""Cached metric-calculation functions for model quality and driver consistency."""

from __future__ import annotations

from typing import Dict, Union

import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def calculate_model_metrics(
    lap_summary: pd.DataFrame, models: dict
) -> Dict[str, Dict[str, Union[float, int]]]:
    """Calcula métricas de calidad del modelo (MAE, R²)."""
    metrics: Dict[str, Dict[str, Union[float, int]]] = {}
    if lap_summary.empty or not models:
        return metrics

    for compound, params in models.items():
        if len(params) >= 2:
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
                actual = compound_data["lap_time_s"]

                mae = abs(predictions - actual).mean()

                ss_res = ((actual - predictions) ** 2).sum()
                ss_tot = ((actual - actual.mean()) ** 2).sum()
                r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

                metrics[compound] = {
                    "mae": mae,
                    "r2": r2,
                    "samples": len(compound_data),
                }

    return metrics


@st.cache_data(show_spinner=False)
def calculate_consistency_metrics(
    lap_summary: pd.DataFrame,
) -> Dict[str, Dict[str, Union[float, int]]]:
    """Calcula métricas de consistencia del piloto."""
    metrics: Dict[str, Dict[str, Union[float, int]]] = {}
    if lap_summary.empty:
        return metrics

    if "compound" in lap_summary.columns and "lap_time_s" in lap_summary.columns:
        consistency = lap_summary.groupby("compound")["lap_time_s"].agg(
            ["std", "mean", "count"]
        )
        for compound, row in consistency.iterrows():
            compound_str = str(compound)
            if row["count"] >= 3:
                cv = (row["std"] / row["mean"]) * 100
                metrics[compound_str] = {
                    "std": row["std"],
                    "mean": row["mean"],
                    "cv_percent": cv,
                    "samples": row["count"],
                }

    return metrics
