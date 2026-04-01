"""Shared imports and project-root path setup.

All f1m imports go through here so the sys.path fix runs exactly once,
regardless of the working directory when Streamlit is launched.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, Union

import pandas as pd

try:
    import plotly.express as px
    import plotly.graph_objects as go

    _PLOTLY_AVAILABLE = True
except ImportError:
    px = None  # type: ignore[assignment]
    go = None  # type: ignore[assignment]
    _PLOTLY_AVAILABLE = False

# Ensure project root is on sys.path so f1m is importable regardless of CWD.
# __file__ is app/_imports.py → parents[1] is the project root.
try:
    from f1m.common import collect_practice_data
    from f1m.modeling import adjust_lap_time_for_conditions, fit_degradation_model
    from f1m.planner import enumerate_plans, live_pit_recommendation
    from f1m.telemetry import (
        COL_COMPOUND,
        COL_LAP,
        COL_LAP_TIME,
        COL_RAIN,
        COL_SAFETY_CAR,
        COL_TIRE_AGE,
        DIR_MODELS,
        build_lap_summary,
        build_stints,
        detect_pit_events,
        fia_compliance_check,
        load_session_csv,
    )
except ImportError:
    _project_root = Path(__file__).resolve().parents[1]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from f1m.common import collect_practice_data
    from f1m.modeling import adjust_lap_time_for_conditions, fit_degradation_model
    from f1m.planner import enumerate_plans, live_pit_recommendation
    from f1m.telemetry import (
        COL_COMPOUND,
        COL_LAP,
        COL_LAP_TIME,
        COL_RAIN,
        COL_SAFETY_CAR,
        COL_TIRE_AGE,
        DIR_MODELS,
        build_lap_summary,
        build_stints,
        detect_pit_events,
        fia_compliance_check,
        load_session_csv,
    )

__all__ = [
    "json",
    "sys",
    "datetime",
    "Path",
    "Dict",
    "Iterable",
    "Optional",
    "Tuple",
    "Union",
    "pd",
    "px",
    "go",
    "_PLOTLY_AVAILABLE",
    "collect_practice_data",
    "adjust_lap_time_for_conditions",
    "fit_degradation_model",
    "enumerate_plans",
    "live_pit_recommendation",
    "COL_COMPOUND",
    "COL_LAP",
    "COL_LAP_TIME",
    "COL_RAIN",
    "COL_SAFETY_CAR",
    "COL_TIRE_AGE",
    "DIR_MODELS",
    "build_lap_summary",
    "build_stints",
    "detect_pit_events",
    "fia_compliance_check",
    "load_session_csv",
]
