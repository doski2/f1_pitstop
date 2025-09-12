# f1m package: utilidades de telemetría, modelado y planificación
from .modeling import (
    collect_practice_data,
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
