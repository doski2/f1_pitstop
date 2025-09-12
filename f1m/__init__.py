# f1m package: utilidades de telemetría, modelado y planificación
from .telemetry import (
    load_session_csv, detect_pit_events, build_lap_summary, build_stints, fia_compliance_check, Stint
)
from .modeling import (
    collect_practice_data, fit_degradation_model, stint_time, max_stint_length
)
from .planner import enumerate_plans, live_pit_recommendation
