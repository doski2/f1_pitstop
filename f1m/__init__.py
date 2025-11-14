# f1m package: utilidades de telemetría, modelado y planificación

from .common import PRACTICE_SESSION_NAMES, collect_practice_data
from .imports import (
    Dict,
    List,
    Optional,
    Path,
    Tuple,
    Union,
    np,
    optimize_dataframe_memory,
    pd,
)
from .modeling import (
    fit_degradation_model,
    max_stint_length,
    stint_time,
)
from .planner import enumerate_plans, live_pit_recommendation
from .telemetry import (
    Stint,
    build_lap_summary,
    build_stints,
    detect_pit_events,
    fia_compliance_check,
    load_session_csv,
)

# Hace que 'f1m' sea un paquete estándar para importaciones fiables.
__all__: list[str] = []
