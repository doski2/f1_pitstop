"""Shared fixtures for the f1m test suite.

All fixtures produce synthetic data — no real CSV files needed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Basic lap-level DataFrame used by telemetry / modeling tests
# ---------------------------------------------------------------------------

def _make_laps(
    n: int = 20,
    compound: str = "Soft",
    base_time: float = 90.0,
    deg: float = 0.15,
    pit_laps: tuple[int, ...] = (),
    session: str = "Practice 1",
) -> pd.DataFrame:
    """Return a minimal lap-summary DataFrame with realistic F1 values."""
    rows = []
    tire_age = 0
    for lap in range(1, n + 1):
        in_pit = lap in pit_laps
        if in_pit:
            tire_age = 0
        lap_time = base_time + deg * tire_age + np.random.normal(0, 0.05)
        rows.append(
            {
                "currentLap": lap,
                "lap_time_s": None if in_pit else round(lap_time, 4),
                "compound": compound,
                "tire_age": tire_age,
                "trackTemp": 32.0,
                "airTemp": 26.0,
                "flTemp": 105.0,
                "frTemp": 105.0,
                "rlTemp": 100.0,
                "rrTemp": 100.0,
                "fuel": round(110.0 - 1.4 * lap, 2),
                "pit_stop": in_pit,
                "tire_change_pit": in_pit,
                "safety_car": False,
                "rain": False,
                "paceMode": "Standard",
                "session": session,
            }
        )
        tire_age += 1
    return pd.DataFrame(rows)


@pytest.fixture()
def soft_laps() -> pd.DataFrame:
    np.random.seed(0)
    return _make_laps(20, "Soft", 90.0, 0.18)


@pytest.fixture()
def medium_laps() -> pd.DataFrame:
    np.random.seed(1)
    return _make_laps(25, "Medium", 91.5, 0.10)


@pytest.fixture()
def hard_laps() -> pd.DataFrame:
    np.random.seed(2)
    return _make_laps(30, "Hard", 93.0, 0.05)


@pytest.fixture()
def multi_compound_laps(soft_laps, medium_laps, hard_laps) -> pd.DataFrame:
    """Combined practice dataset with three compounds."""
    return pd.concat([soft_laps, medium_laps, hard_laps], ignore_index=True)


@pytest.fixture()
def simple_models() -> dict:
    """Pre-baked 2-param (intercept, slope) models for Soft / Medium / Hard."""
    return {
        "Soft":   (90.0, 0.18),
        "Medium": (91.5, 0.10),
        "Hard":   (93.0, 0.05),
    }


# ---------------------------------------------------------------------------
# Minimal raw-telemetry DataFrame (row-per-sample, not per-lap)
# ---------------------------------------------------------------------------

@pytest.fixture()
def raw_telemetry_df() -> pd.DataFrame:
    """Simulates the output of load_session_csv for a short stint."""
    n_rows = 100
    laps = np.repeat(np.arange(1, 11), n_rows // 10)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-04-05 20:00:00", periods=n_rows, freq="50ms"),
            "currentLap": laps,
            "lastLapTime": [90.5] * n_rows,
            "compound": ["Soft"] * n_rows,
            "tire_age": np.tile(np.arange(10), n_rows // 10),
            "pitstopStatus": ["On Track"] * n_rows,
            "trackTemp": [32.0] * n_rows,
            "airTemp": [26.0] * n_rows,
            "flTemp": [105.0] * n_rows,
            "frTemp": [105.0] * n_rows,
            "rlTemp": [100.0] * n_rows,
            "rrTemp": [100.0] * n_rows,
            "fuel": np.linspace(110, 96, n_rows),
            "flDeg": [0.95] * n_rows,
            "frDeg": [0.95] * n_rows,
            "rlDeg": [0.97] * n_rows,
            "rrDeg": [0.97] * n_rows,
            "paceMode": ["Standard"] * n_rows,
            "safety_car": [False] * n_rows,
            "rain": [False] * n_rows,
        }
    )


# ---------------------------------------------------------------------------
# CSV file helpers
# ---------------------------------------------------------------------------

MINIMAL_CSV_HEADER = (
    "timestamp,currentLap,lastLapTime,compound,tire_age,pitstopStatus,"
    "trackTemp,airTemp,flTemp,frTemp,rlTemp,rrTemp,fuel\n"
)


def _csv_row(ts: str, lap: int, lap_time: float, compound: str, age: int) -> str:
    return (
        f"{ts},{lap},{lap_time},{compound},{age},On Track,"
        f"32.0,26.0,105.0,105.0,100.0,100.0,{110 - 1.4 * lap:.2f}\n"
    )


@pytest.fixture()
def single_csv_dir(tmp_path: Path) -> Path:
    """A directory containing a single CSV file (10 laps)."""
    f = tmp_path / "2026-04-05_20-00-00_AstonMartin1_Telemetry_Bahrain_Race.csv"
    content = MINIMAL_CSV_HEADER
    for lap in range(1, 11):
        ts = f"2026-04-05 20:{lap:02d}:00.000"
        content += _csv_row(ts, lap, 90.5, "Soft", lap - 1)
    f.write_text(content, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def multi_csv_dir(tmp_path: Path) -> Path:
    """Two CSV files simulating a race paused after lap 10 and resumed."""
    # File 1: laps 1-10
    f1 = tmp_path / "2026-04-05_20-00-00_AstonMartin1_Telemetry_Bahrain_Race.csv"
    content1 = MINIMAL_CSV_HEADER
    for lap in range(1, 11):
        ts = f"2026-04-05 20:{lap:02d}:00.000"
        content1 += _csv_row(ts, lap, 90.5, "Soft", lap - 1)
    f1.write_text(content1, encoding="utf-8")

    # File 2: laps 11-20 (new file after resume)
    f2 = tmp_path / "2026-04-05_21-00-00_AstonMartin1_Telemetry_Bahrain_Race.csv"
    content2 = MINIMAL_CSV_HEADER
    for lap in range(11, 21):
        ts = f"2026-04-05 21:{lap - 10:02d}:00.000"
        content2 += _csv_row(ts, lap, 90.5, "Soft", lap - 1)
    f2.write_text(content2, encoding="utf-8")

    return tmp_path


@pytest.fixture()
def overlapping_csv_dir(tmp_path: Path) -> Path:
    """Two files sharing the last 3 rows (overlap at the split point)."""
    f1 = tmp_path / "2026-04-05_20-00-00_AstonMartin1_Telemetry_Bahrain_Race.csv"
    content1 = MINIMAL_CSV_HEADER
    for lap in range(1, 11):
        ts = f"2026-04-05 20:{lap:02d}:00.000"
        content1 += _csv_row(ts, lap, 90.5, "Soft", lap - 1)
    f1.write_text(content1, encoding="utf-8")

    f2 = tmp_path / "2026-04-05_21-00-00_AstonMartin1_Telemetry_Bahrain_Race.csv"
    # Laps 8-9-10 duplicated, then new laps 11-20
    content2 = MINIMAL_CSV_HEADER
    for lap in list(range(8, 11)) + list(range(11, 21)):
        ts = f"2026-04-05 20:{lap:02d}:00.000" if lap <= 10 else f"2026-04-05 21:{lap - 10:02d}:00.000"
        content2 += _csv_row(ts, lap, 90.5, "Soft", lap - 1)
    f2.write_text(content2, encoding="utf-8")

    return tmp_path
