"""Shared imports and project-root path setup.

All f1m imports go through here so the sys.path fix runs exactly once,
regardless of the working directory when Streamlit is launched.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

# ── Python 3.13 compat ──────────────────────────────────────────────────────
# Python 3.13.5 simplified json.dumps to `JSONEncoder(**kw).encode(obj)`,
# removing special handling for the `cls` kwarg.  Restore it so that
# third-party libs (Plotly, etc.) that call json.dumps(obj, cls=X) still work.
if not hasattr(json.dumps, "_patched_cls"):
    _json_dumps_orig = json.dumps

    def _json_dumps_compat(obj, **kw):  # type: ignore[misc]
        cls = kw.pop("cls", None)
        if cls is not None:
            return cls(**kw).encode(obj)
        return _json_dumps_orig(obj, **kw)

    _json_dumps_compat._patched_cls = True  # type: ignore[attr-defined]
    json.dumps = _json_dumps_compat  # type: ignore[assignment]
# ────────────────────────────────────────────────────────────────────────────

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
    from f1m.common import (
        canonical_compound,
        collect_practice_data,
        compound_color,
        display_compound,
    )
    from f1m.constants import (
        COMPOUND_CANONICAL_MAP,
        COMPOUND_COLOR_MAP,
        COMPOUND_DISPLAY_MAP,
    )
    from f1m.modeling import adjust_lap_time_for_conditions, fit_degradation_model
    from f1m.planner import (
        enumerate_plans,
        live_pit_recommendation,
        plan_aware_recommendation,
    )
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
        load_multi_session_csvs,
        load_session_csv,
    )
except ImportError:
    _project_root = Path(__file__).resolve().parents[1]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from f1m.common import (
        canonical_compound,
        collect_practice_data,
        compound_color,
        display_compound,
    )
    from f1m.constants import (
        COMPOUND_CANONICAL_MAP,
        COMPOUND_COLOR_MAP,
        COMPOUND_DISPLAY_MAP,
    )
    from f1m.modeling import adjust_lap_time_for_conditions, fit_degradation_model
    from f1m.planner import (
        enumerate_plans,
        live_pit_recommendation,
        plan_aware_recommendation,
    )
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
        load_multi_session_csvs,
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
    "plan_aware_recommendation",
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
    "load_multi_session_csvs",
    "load_session_csv",
    "display_compound",
    "canonical_compound",
    "compound_color",
    "COMPOUND_CANONICAL_MAP",
    "COMPOUND_COLOR_MAP",
    "COMPOUND_DISPLAY_MAP",
]
