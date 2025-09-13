from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Asegura que el módulo 'strategy.py' (ubicado en app/) sea importable
_BASE = Path(__file__).resolve().parent.parent
_APP_DIR = _BASE / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

# Reemplazar la importación directa que fallaba para linters/IDE y en tiempo de ejecución
try:
    # Import preferente como paquete (ayuda a herramientas estáticas)
    from app.strategy import load_session_csv  # type: ignore
except Exception:
    # Fallback: cargar dinámicamente desde app/strategy.py usando importlib
    try:
        strategy_path = _APP_DIR / "strategy.py"
        if strategy_path.exists():
            import importlib.util

            spec = importlib.util.spec_from_file_location("app.strategy", str(strategy_path))
            module = importlib.util.module_from_spec(spec)  # type: ignore
            assert spec and spec.loader
            spec.loader.exec_module(module)  # type: ignore
            load_session_csv = getattr(module, "load_session_csv")
        else:
            # Intentar importar como módulo plano si está en sys.path
            from strategy import load_session_csv  # type: ignore
    except Exception as e:
        raise ImportError(
            "No se pudo importar 'strategy'. Verifica que exista app/strategy.py y que la ruta sea correcta."
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
        except Exception:  # pragma: no cover
            pass
    # Si ya están alineadas las columnas no hacemos más cambios.
    return df
