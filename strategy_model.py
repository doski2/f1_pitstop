"""
Shim de compatibilidad: re-exporta desde f1m.modeling y f1m.planner.
Permite a código existente seguir importando `strategy_model`.
"""
from f1m.modeling import *  # noqa: F401,F403
from f1m.planner import *  # noqa: F401,F403
