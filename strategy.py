"""
Shim de compatibilidad: re-exporta desde f1m.telemetry.
Permite a código existente seguir importando `strategy`.
"""

from f1m.telemetry import *  # noqa: F401,F403
