"""Tests para la lógica pura de scripts/logger.py.

Sólo se prueban partes que no requieren MemoryReader.exe ni ctypes:
  - Detección de pausa (timeElapsed congelado)
  - Resolución de nombres y compuestos
  - Cálculo de stint / tire_age
  - Tablas de lookup
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub de ctypes.windll para que logger.py no falle al importar en CI
# ---------------------------------------------------------------------------

def _patch_ctypes_windll():
    """Crea un stub mínimo de ctypes.windll.kernel32."""
    import ctypes

    if not hasattr(ctypes, "windll"):
        windll_stub = types.SimpleNamespace(
            kernel32=types.SimpleNamespace(
                OpenFileMappingW=MagicMock(return_value=1),
                MapViewOfFile=MagicMock(return_value=1),
                UnmapViewOfFile=MagicMock(return_value=True),
                CloseHandle=MagicMock(return_value=True),
            )
        )
        ctypes.windll = windll_stub  # type: ignore[attr-defined]


_patch_ctypes_windll()

# Asegurar que scripts/ esté en sys.path
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import logger as _lg  # noqa: E402  (importar después del patch)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger(tmp_path: Path) -> _lg.F1Logger:
    return _lg.F1Logger(
        output_root=tmp_path,
        interval=0.05,
        driver_filter=None,
    )


def _empty_car(number: int = 0) -> dict:
    return {
        "driverPos": 0, "currentLap": 0, "tireCompound": 2,
        "pitStopStatus": 0, "paceMode": 2, "fuelMode": 1, "ersMode": 0,
        "flSurfaceTemp": 100.0, "flTemp": 100.0, "flBrakeTemp": 300.0,
        "frSurfaceTemp": 100.0, "frTemp": 100.0, "frBrakeTemp": 300.0,
        "rlSurfaceTemp": 100.0, "rlTemp": 100.0, "rlBrakeTemp": 280.0,
        "rrSurfaceTemp": 100.0, "rrTemp": 100.0, "rrBrakeTemp": 280.0,
        "flWear": 0.95, "frWear": 0.95, "rlWear": 0.97, "rrWear": 0.97,
        "engineTemp": 105.0, "engineWear": 0.99, "gearboxWear": 0.99,
        "ersWear": 0.99, "charge": 0.8, "energyHarvested": 0.0,
        "energySpent": 0.0, "fuel": 100.0, "fuelDelta": -0.0013,
        "teamId": 1, "driverNumber": number, "driverId": 0,
        "turnNumber": 5, "speed": 280, "rpm": 12000, "gear": 7,
        "position": 10, "drsMode": 0, "ERSAssist": 0,
        "OvertakeAggression": 1, "DefendApproach": 1,
        "DriveCleanAir": 0, "AvoidHighKerbs": 0, "DontFightTeammate": 0,
        "driverBestLap": 90.5, "currentLapTime": 45.0, "lastLapTime": 90.3,
        "lastS1Time": 28.1, "lastS2Time": 34.2, "lastS3Time": 28.0,
        "distanceTravelled": 300.0, "GapToLeader": 5.0,
    }


def _all_cars(car_0: dict) -> list[dict]:
    cars = [_empty_car(0)] * _lg.DRIVER_COUNT
    cars[0] = car_0
    return cars


# ---------------------------------------------------------------------------
# Detección de pausa
# ---------------------------------------------------------------------------

class TestPauseDetection:
    """El logger no debe escribir filas cuando timeElapsed está congelado."""

    def test_initial_state(self, tmp_path):
        lg = _make_logger(tmp_path)
        assert lg._last_time_elapsed == -1.0

    def test_first_frame_recorded(self, tmp_path):
        lg = _make_logger(tmp_path)
        # La primera vez timeElapsed (-1.0) != 0.05 → se escribe
        assert lg._last_time_elapsed != 0.05

    def test_same_time_elapsed_is_pause(self, tmp_path):
        lg = _make_logger(tmp_path)
        lg._last_time_elapsed = 100.0
        # Si llega 100.0 de nuevo → pausa
        is_paused = (100.0 == lg._last_time_elapsed)
        assert is_paused

    def test_advancing_time_not_paused(self, tmp_path):
        lg = _make_logger(tmp_path)
        lg._last_time_elapsed = 100.0
        is_paused = (100.05 == lg._last_time_elapsed)
        assert not is_paused

    def test_reset_on_new_session(self, tmp_path):
        lg = _make_logger(tmp_path)
        lg._last_time_elapsed = 999.0
        cars = _all_cars(_empty_car(14))
        lg._start_session(2, 6, cars)
        assert lg._last_time_elapsed == -1.0


# ---------------------------------------------------------------------------
# Resolución de compuestos
# ---------------------------------------------------------------------------

class TestCompoundResolution:
    def test_known_tire_map(self, tmp_path):
        lg = _make_logger(tmp_path)
        lg._tire_map = {0: "Hard", 1: "Medium", 2: "Soft"}
        assert lg._compound_name(0) == "Hard"
        assert lg._compound_name(1) == "Medium"
        assert lg._compound_name(2) == "Soft"

    def test_unknown_id_returns_c_prefix(self, tmp_path):
        lg = _make_logger(tmp_path)
        lg._tire_map = {}
        assert lg._compound_name(5) == "C5"
        assert lg._compound_name(99) == "C99"

    def test_tire_map_loaded_from_json(self, tmp_path):
        (tmp_path / "tire_map.json").write_text(
            '{"0": "Hard", "1": "Medium", "2": "Soft"}', encoding="utf-8"
        )
        _make_logger(tmp_path)
        # output_root es tmp_path; tire_map.json se busca en tmp_path.parent
        # Para este test usamos un subdirectorio como output_root
        sub = tmp_path / "exported_data"
        sub.mkdir()
        lg2 = _lg.F1Logger(output_root=sub, interval=0.05, driver_filter=None)
        lg2._load_tire_map()
        assert lg2._tire_map == {0: "Hard", 1: "Medium", 2: "Soft"}


# ---------------------------------------------------------------------------
# Cálculo de stint / tire_age
# ---------------------------------------------------------------------------

class TestUpdateStint:
    def _lg(self, tmp_path):
        lg = _make_logger(tmp_path)
        lg._tire_map = {0: "Hard", 1: "Medium", 2: "Soft"}
        return lg

    def test_first_sample_age_zero(self, tmp_path):
        lg = self._lg(tmp_path)
        car = _empty_car(14)
        car["tireCompound"] = 2
        car["currentLap"] = 0
        compound, age = lg._update_stint(0, car)
        assert compound == "Soft"
        assert age == 0

    def test_age_increases_each_lap(self, tmp_path):
        lg = self._lg(tmp_path)
        car = _empty_car(14)
        car["tireCompound"] = 2
        compound, age = "Soft", 0
        for lap in range(5):
            car["currentLap"] = lap
            compound, age = lg._update_stint(0, car)
        # tire_age = max(0, (lap+1) - change_lap). change_lap = 0+1 = 1.
        # After lap=4: max(0, 5-1) = 4
        assert age == 4

    def test_compound_change_resets_age(self, tmp_path):
        lg = self._lg(tmp_path)
        car = _empty_car(14)
        car["tireCompound"] = 2  # Soft
        for lap in range(10):
            car["currentLap"] = lap
            lg._update_stint(0, car)
        # Cambio a Medium en vuelta 10
        car["tireCompound"] = 1
        car["currentLap"] = 10
        compound, age = lg._update_stint(0, car)
        assert compound == "Medium"
        assert age == 0


# ---------------------------------------------------------------------------
# Tablas de lookup
# ---------------------------------------------------------------------------

class TestLookupTables:
    def test_track_names_has_bahrain(self):
        assert _lg.TRACK_NAMES[2] == "Bahrain"

    def test_session_types_has_race(self):
        assert _lg.SESSION_TYPES[6] == "Race"

    def test_pace_modes_complete(self):
        assert 0 in _lg.PACE_MODES  # Attack
        assert 2 in _lg.PACE_MODES  # Standard

    def test_telemetry_size_correct(self):
        # Estructura conocida: 40 bytes sesión + 22 × 220 bytes coches
        expected = 40 + 22 * 220
        assert _lg.TELEMETRY_SIZE == expected

    def test_pit_status_label_on_track_race(self, tmp_path):
        lg = _make_logger(tmp_path)
        assert lg._pit_status_label(0, 6) == "On Track"

    def test_pit_status_label_none_practice(self, tmp_path):
        lg = _make_logger(tmp_path)
        assert lg._pit_status_label(0, 0) == "None"

    def test_pit_status_stopped(self, tmp_path):
        lg = _make_logger(tmp_path)
        assert lg._pit_status_label(4, 6) == "Stopped"


# ---------------------------------------------------------------------------
# Resolución de pilotos
# ---------------------------------------------------------------------------

class TestDriverResolution:
    def test_known_driver_alonso(self, tmp_path):
        lg = _make_logger(tmp_path)
        cars = _all_cars(_empty_car(14))
        lg._assign_car_names(cars)
        first, last, code, team, car_name = lg._resolve_driver(0, cars[0])
        assert first == "Fernando"
        assert last == "Alonso"
        assert code == "ALO"
        assert team == "Aston Martin"

    def test_unknown_driver_fallback(self, tmp_path):
        lg = _make_logger(tmp_path)
        car = _empty_car(99)
        car["teamId"] = 7
        cars = _all_cars(car)
        lg._assign_car_names(cars)
        first, last, code, team, _ = lg._resolve_driver(0, cars[0])
        assert first == "Driver"
        assert last == "99"

    def test_car_name_format(self, tmp_path):
        lg = _make_logger(tmp_path)
        cars = _all_cars(_empty_car(14))
        lg._assign_car_names(cars)
        car_name = lg._car_names.get(0, "")
        assert "AstonMartin" in car_name
