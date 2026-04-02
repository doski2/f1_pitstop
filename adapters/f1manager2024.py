from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Asegura que el módulo 'f1m' sea importable
_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

# Importar desde f1m.telemetry
try:
    from f1m.telemetry import load_session_csv
except (ModuleNotFoundError, ImportError) as e:
    raise ImportError(
        "No se pudo importar desde 'f1m.telemetry'. Verifica que el paquete f1m esté correctamente instalado."
    ) from e


def load_raw_csv(path: str | Path) -> pd.DataFrame:
    """Carga y normaliza un CSV exportado de F1 Manager 2024.

    Retorna DataFrame con columnas (si existen en origen) mapeadas al esquema canónico.
    No fuerza la creación de columnas ausentes; sólo garantiza timestamp ordenado.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {csv_path}")
    # load_session_csv ya convierte timestamp y ordena; no se necesita postproceso.
    return load_session_csv(csv_path)
