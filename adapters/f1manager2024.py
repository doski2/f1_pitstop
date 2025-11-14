from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Asegura que el módulo 'f1m' sea importable
_BASE = Path(__file__).resolve().parent.parent
_F1M_DIR = _BASE / "f1m"
if str(_F1M_DIR) not in sys.path:
    sys.path.insert(0, str(_F1M_DIR))

# Importar desde f1m.telemetry
try:
    from f1m.telemetry import load_session_csv
except Exception as e:
    raise ImportError(
        "No se pudo importar desde 'f1m.telemetry'. Verifica que el paquete f1m esté correctamente instalado."
    ) from e


CANONICAL_COLS = [
    "currentLap",
    "timestamp",
    "compound",
    "tire_age",
    "lap_time_s",
    "fuel",
    "flTemp",
    "frTemp",
    "rlTemp",
    "rrTemp",
    "trackTemp",
    "airTemp",
]


def load_raw_csv(path: str | Path) -> pd.DataFrame:
    """Carga y normaliza un CSV exportado de F1 Manager 2024.

    Retorna DataFrame con columnas (si existen en origen) mapeadas al esquema canónico.
    No fuerza la creación de columnas ausentes; sólo garantiza timestamp ordenado.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {csv_path}")
    df = load_session_csv(csv_path)
    # Asegura orden por timestamp si está disponible
    if "timestamp" in df.columns:
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
        except (ValueError, TypeError):  # pragma: no cover
            pass
    # Si ya están alineadas las columnas no hacemos más cambios.
    return df
