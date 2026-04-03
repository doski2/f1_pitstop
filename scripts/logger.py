#!/usr/bin/env python3
"""scripts/logger.py

Lector Python del Memory Mapped File "F1ManagerTelemetry" creado por
MemoryReader.exe.  Exporta telemetría a CSV en el mismo formato que
el plugin de SimHub, eliminando esa dependencia por completo.

Requisito previo
----------------
MemoryReader.exe (del repositorio Asviix/F1Manager2024Logger) debe estar
corriendo ANTES de iniciar este script.  El ejecutable lee la memoria del
proceso F1Manager24.exe y escribe los datos en un MMF llamado
"F1ManagerTelemetry".  Este script lee ese MMF — NOT requiere SimHub.

Uso
---
    python scripts/logger.py
    python scripts/logger.py --output ruta/a/logs_in/exported_data
    python scripts/logger.py --interval 0.1   # polling cada 100 ms
    python scripts/logger.py --drivers 14 18  # filtrar pilotos por número

Compuestos de neumáticos
------------------------
El ID del compuesto en el MMF es un índice de "tire set" que requiere el
fichero de savedata del juego para resolverse a Soft/Medium/Hard.
Sin ese fichero se usa "C{id}" como etiqueta.  Puedes crear el fichero
  logs_in/tire_map.json
con el formato {"0": "Soft", "1": "Medium", "2": "Hard", ...} para
sobreescribir las etiquetas.  El script lo recarga automáticamente cada
sesión.  El análisis de stint funciona correctamente con etiquetas numéricas
ya que sólo requiere detectar cambios de compuesto, no sus nombres.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import signal
import struct
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Rutas base
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent.parent
_DEFAULT_OUTPUT = _BASE / "logs_in" / "exported_data"

# ---------------------------------------------------------------------------
# Constantes del MMF
# ---------------------------------------------------------------------------
MMF_NAME = "F1ManagerTelemetry"
DRIVER_COUNT = 22
DEFAULT_INTERVAL = 0.05       # 50 ms → ~20 muestras/s
DEFAULT_RECONNECT_DELAY = 5.0 # segundos entre reintentos de conexión

# ---------------------------------------------------------------------------
# Formato binario del struct Telemetry (Pack = 1, little-endian)
#
# Estructura C# (MmfReader.cs / MemoryReader/Program.cs):
#
#   struct Telemetry {
#     SessionTelemetry Session;   → ffiiffifif  (40 bytes)
#     int  cameraFocus;           ┐
#     float carFloatValue;        ┘ contenido en fmto. sesión
#     CarTelemetry[22] Car;       → 22 × 220 bytes
#   }
#
#   struct SessionTelemetry {           struct WeatherTelemetry {
#     float timeElapsed;                  float airTemp;
#     float rubber;                       float trackTemp;
#     int   trackId;                      int   weather;
#     int   sessionType;                  float waterOnTrack;
#     WeatherTelemetry Weather;         }
#   }
#
#   struct CarTelemetry {                  struct DriverTelemetry {
#     int   driverPos;                       int   teamId;         │
#     int   currentLap;                      int   driverNumber;   │
#     int   tireCompound;                    int   driverId;       │
#     int   pitStopStatus;                   int   turnNumber;     │
#     int   paceMode;                        int   speed;          │
#     int   fuelMode;                        int   rpm;            │ 15 ints
#     int   ersMode;                         int   gear;           │
#     float flSurfaceTemp; ┐                 int   position;       │
#     float flTemp;        │                 int   drsMode;        │
#     float flBrakeTemp;   │                 int   ERSAssist;      │
#     float frSurfaceTemp; │                 int   OvertakeAgg.;   │
#     float frTemp;        │                 int   DefendApproach; │
#     float frBrakeTemp;   │                 int   DriveCleanAir;  │
#     float rlSurfaceTemp; │ 25 floats       int   AvoidHighKerbs; │
#     float rlTemp;        │                 int   DontFightTmmt.; ┘
#     float rlBrakeTemp;   │                 float driverBestLap;  ┐
#     float rrSurfaceTemp; │                 float currentLapTime; │
#     float rrTemp;        │                 float lastLapTime;    │
#     float rrBrakeTemp;   │                 float lastS1Time;     │ 8 floats
#     float flWear;        │                 float lastS2Time;     │
#     float frWear;        │                 float lastS3Time;     │
#     float rlWear;        │                 float distTravel;     │
#     float rrWear;        │                 float GapToLeader;    ┘
#     float engineTemp;    │             }
#     float engineWear;    │
#     float gearboxWear;   │
#     float ersWear;       │
#     float charge;        │
#     float energyHarv.;   │
#     float energySpent;   ┘
#     float fuel;
#     float fuelDelta;
#     DriverTelemetry Driver;
#   }
# ---------------------------------------------------------------------------
_SESSION_FMT = "ffiiffifif"    # 10 campos = 40 bytes
_CAR_FMT     = "7i25f15i8f"   # 55 campos = 220 bytes
STRUCT_FORMAT = "<" + _SESSION_FMT + _CAR_FMT * DRIVER_COUNT
TELEMETRY_SIZE = struct.calcsize(STRUCT_FORMAT)  # debe ser 4880

_SESSION_FIELDS   = 10
_FIELDS_PER_CAR   = 55

# ---------------------------------------------------------------------------
# Tablas de lookup  (extraídas de TelemetryHelpers.cs)
# ---------------------------------------------------------------------------
TRACK_NAMES: dict[int, str] = {
    0:  "Invalid",
    1:  "Albert Park",
    2:  "Bahrain",
    3:  "Shanghai",
    4:  "Baku",
    5:  "Barcelona",
    6:  "Monaco",
    7:  "Montreal",
    8:  "Paul Ricard",
    9:  "Red Bull Ring",
    10: "Silverstone",
    11: "Jeddah",
    12: "Hungaroring",
    13: "Spa-Francorchamps",
    14: "Monza",
    15: "Marina Bay",
    16: "Sochi",
    17: "Suzuka",
    18: "Hermanos Rodriguez",
    19: "Circuit of the Americas",
    20: "Interlagos",
    21: "Yas Marina",
    22: "Miami",
    23: "Zandvoort",
    24: "Imola",
    25: "Las Vegas",
    26: "Qatar",
}

SESSION_TYPES: dict[int, str] = {
    0:  "Practice 1",
    1:  "Practice 2",
    2:  "Practice 3",
    3:  "Qualifying 1",
    4:  "Qualifying 2",
    5:  "Qualifying 3",
    6:  "Race",
    7:  "Sprint",
    8:  "Sprint Qualifying 1",
    9:  "Sprint Qualifying 2",
    10: "Sprint Qualifying 3",
}

# Duración en minutos por tipo de sesión (0 = determinado por vueltas)
SESSION_LENGTH_MIN: dict[int, int] = {
    0: 60, 1: 60, 2: 60,       # Practice 1-3
    3: 18, 4: 15, 5: 12,        # Q1, Q2, Q3
    6: 0,  7: 0,                 # Race, Sprint  (por vueltas)
    8: 12, 9: 10, 10: 8,        # SQ1, SQ2, SQ3
}

# Número de vueltas por circuito
TRACK_LAPS: dict[int, int] = {
    0:  0,   1: 58,  2: 57,  3: 56,  4: 51,  5: 66,
    6:  78,  7: 70,  8: 53,  9: 71, 10: 52, 11: 50,
    12: 70, 13: 44, 14: 53, 15: 62, 16: 53, 17: 53,
    18: 71, 19: 56, 20: 71, 21: 58, 22: 57, 23: 72,
    24: 63, 25: 50, 26: 57,
}

TRACK_LAPS_SPRINT: dict[int, int] = {
    0:  0,  1: 19,  2: 19,  3: 19,  4: 17,  5: 22,
    6: 30,  7: 23,  8: 18,  9: 24, 10: 17, 11: 17,
    12: 23, 13: 15, 14: 18, 15: 21, 16: 18, 17: 18,
    18: 24, 19: 19, 20: 24, 21: 19, 22: 19, 23: 24,
    24: 17, 25: 17, 26: 19,
}

PACE_MODES:    dict[int, str] = {0: "Attack", 1: "Aggressive", 2: "Standard", 3: "Light", 4: "Conserve"}
FUEL_MODES:    dict[int, str] = {0: "Push",   1: "Balanced",   2: "Conserve"}
ERS_MODES:     dict[int, str] = {0: "Neutral", 1: "Harvest", 2: "Deploy", 3: "Top Up"}
DRS_MODES:     dict[int, str] = {0: "Disabled", 1: "Detected", 2: "Enabled", 3: "Active"}
OVERTAKE_MODES:dict[int, str] = {0: "High", 1: "Medium", 2: "Low"}
DEFEND_MODES:  dict[int, str] = {0: "Always", 1: "Neutral", 2: "Rarely"}
WEATHER_TYPES: dict[int, str] = {
    0: "None", 1: "Sunny", 2: "Partly Sunny", 3: "Cloudy",
    4: "Light Rain", 5: "Moderate Rain", 16: "Heavy Rain",
}

PIT_STATUSES: dict[int, str] = {
    0: "On Track",  1: "Requested", 2: "Entering",  3: "Queuing",
    4: "Stopped",   5: "Exiting",   6: "In Garage",  7: "Jack Up",
    8: "Releasing", 9: "Car Setup", 10: "Approach", 11: "Penalty",
    12: "Releasing",
}

# Distancia en metros desde la línea de meta al Speed Trap de cada circuito
# (extraída de TelemetryHelpers.cs → GetSpeedTrapDistance)
SPEED_TRAP_DIST: dict[int, float] = {
    0:  0.0,
    1:  231.402594,   # Albert Park
    2:  554.268687,   # Bahrain
    3:  4472.886543,  # Shanghai
    4:  5142.278267,  # Baku
    5:  599.251425,   # Barcelona
    6:  1859.776249,  # Monaco
    7:  3550.89665,   # Montreal
    8:  2580.680579,  # Paul Ricard
    9:  2014.860737,  # Red Bull Ring
    10: 4858.272171,  # Silverstone
    11: 5301.036909,  # Jeddah
    12: 315.89929,    # Hungaroring
    13: 1222.67089,   # Spa-Francorchamps
    14: 664.830088,   # Monza
    15: 241.944879,   # Marina Bay
    16: 1070.783823,  # Sochi
    17: 5047.793003,  # Suzuka
    18: 957.583701,   # Hermanos Rodriguez
    19: 3552.430392,  # Circuit of the Americas
    20: 262.152169,   # Interlagos
    21: 2480.84897,   # Yas Marina
    22: 4579.952002,  # Miami
    23: 570.120918,   # Zandvoort
    24: 4197.11918,   # Imola
    25: 5018.287971,  # Las Vegas
    26: 599.526241,   # Qatar
}

# Plantilla de columnas CSV (mismo orden que el plugin original)
CSV_COLUMNS = [
    "timestamp", "trackName", "sessionType", "timeElapsed",
    "Laps/Time Remaining",
    "driverNumber", "driverFirstName", "driverLastName", "driverCode", "teamName",
    "pitstopStatus",
    "currentLap", "turnNumber", "distanceTravelled",
    "position", "gapToLeader", "carInFront", "gapInFront", "carBehind", "gapBehind",
    "compound", "tire_age",
    "flSurfaceTemp", "flTemp", "flBrakeTemp",
    "frSurfaceTemp", "frTemp", "frBrakeTemp",
    "rlSurfaceTemp", "rlTemp", "rlBrakeTemp",
    "rrSurfaceTemp", "rrTemp", "rrBrakeTemp",
    "flDeg", "frDeg", "rlDeg", "rrDeg",
    "speed", "SpeedST", "rpm", "gear",
    "engineTemp", "engineDeg", "gearboxDeg", "ersDeg",
    "charge", "energyHarvested", "energySpent",
    "fuel", "fuelDelta",
    "paceMode", "fuelMode", "ersMode", "drsMode",
    "ersAssist", "driveCleanAir", "avoidHighKerbs", "dontFightTeammate",
    "overtakeAggression", "defendApproach",
    "currentLapTime", "driverBestLap", "lastLapTime",
    "lastS1Time", "driverBestS1Time",
    "lastS2Time", "driverBestS2Time",
    "lastS3Time", "driverBestS3Time",
    "bestSessionTime", "bestS1Time", "bestS2Time", "bestS3Time",
    "rubber", "airTemp", "trackTemp", "weather", "waterOnTrack",
]

# ---------------------------------------------------------------------------
# F1 2024 roster por defecto: número de coche → (nombre, apellido, equipo)
# Actualiza esta tabla para ligas o modos carrera con pilotos distintos.
# ---------------------------------------------------------------------------
# Formato: número → (nombre, apellido, código 3 letras, equipo)
_ROSTER_2024: dict[int, tuple[str, str, str, str]] = {
    1:  ("Max",       "Verstappen",  "VER", "Red Bull"),
    11: ("Sergio",    "Perez",       "PER", "Red Bull"),
    44: ("Lewis",     "Hamilton",    "HAM", "Mercedes"),
    63: ("George",    "Russell",     "RUS", "Mercedes"),
    16: ("Charles",   "Leclerc",     "LEC", "Ferrari"),
    55: ("Carlos",    "Sainz",       "SAI", "Ferrari"),
    81: ("Oscar",     "Piastri",     "PIA", "McLaren"),
    4:  ("Lando",     "Norris",      "NOR", "McLaren"),
    14: ("Fernando",  "Alonso",      "ALO", "Aston Martin"),
    18: ("Lance",     "Stroll",      "STR", "Aston Martin"),
    10: ("Pierre",    "Gasly",       "GAS", "Alpine"),
    31: ("Esteban",   "Ocon",        "OCO", "Alpine"),
    77: ("Valtteri",  "Bottas",      "BOT", "Sauber"),
    24: ("Zhou",      "Guanyu",      "ZHO", "Sauber"),
    20: ("Kevin",     "Magnussen",   "MAG", "Haas"),
    27: ("Nico",      "Hulkenberg",  "HUL", "Haas"),
    3:  ("Daniel",    "Ricciardo",   "RIC", "RB"),
    22: ("Yuki",      "Tsunoda",     "TSU", "RB"),
    23: ("Alexander", "Albon",       "ALB", "Williams"),
    2:  ("Logan",     "Sargeant",    "SAR", "Williams"),
}

# ---------------------------------------------------------------------------
# Acceso a Windows Memory Mapped Files mediante ctypes
# ---------------------------------------------------------------------------
if sys.platform != "win32":
    raise SystemExit("[ERROR] Este script sólo funciona en Windows.")

_k32 = ctypes.windll.kernel32
_k32.OpenFileMappingW.restype  = ctypes.c_void_p
_k32.MapViewOfFile.restype     = ctypes.c_void_p
_k32.UnmapViewOfFile.restype   = ctypes.c_bool
_k32.CloseHandle.restype       = ctypes.c_bool

_FILE_MAP_READ = 0x0004


def _mmf_open(name: str) -> tuple[int, int]:
    """Abre un MMF existente. Retorna (hMapping, pView)."""
    h = _k32.OpenFileMappingW(_FILE_MAP_READ, False, name)
    if not h:
        err = ctypes.get_last_error()
        raise OSError(
            f"No se pudo abrir el MMF '{name}' (código {err}).\n"
            "  → Asegúrate de que MemoryReader.exe esté corriendo."
        )
    ptr = _k32.MapViewOfFile(h, _FILE_MAP_READ, 0, 0, 0)
    if not ptr:
        _k32.CloseHandle(h)
        err = ctypes.get_last_error()
        raise OSError(f"No se pudo mapear la vista del MMF (código {err}).")
    return int(h), int(ptr)


def _mmf_close(h: int, ptr: int) -> None:
    _k32.UnmapViewOfFile(ptr)
    _k32.CloseHandle(h)


def _mmf_read(ptr: int) -> bytes:
    return ctypes.string_at(ptr, TELEMETRY_SIZE)


# ---------------------------------------------------------------------------
# Deserialización del struct binario
# ---------------------------------------------------------------------------
def _unpack(data: bytes) -> Optional[dict]:
    """Convierte los bytes del MMF a un dict con 'session' y 'cars'."""
    if len(data) < TELEMETRY_SIZE:
        return None

    vals = struct.unpack(STRUCT_FORMAT, data)

    session: dict = {
        "timeElapsed":  vals[0],
        "rubber":       vals[1],
        "trackId":      vals[2],
        "sessionType":  vals[3],
        "airTemp":      vals[4],
        "trackTemp":    vals[5],
        "weather":      vals[6],
        "waterOnTrack": vals[7],
        # vals[8]  = cameraFocus   (no se exporta)
        # vals[9]  = carFloatValue (no se exporta)
    }

    cars: list[dict] = []
    for i in range(DRIVER_COUNT):
        o = _SESSION_FIELDS + i * _FIELDS_PER_CAR
        car: dict = {
            # 7 ints (offset 0-6)
            "driverPos":      vals[o],
            "currentLap":     vals[o + 1],
            "tireCompound":   vals[o + 2],
            "pitStopStatus":  vals[o + 3],
            "paceMode":       vals[o + 4],
            "fuelMode":       vals[o + 5],
            "ersMode":        vals[o + 6],
            # 25 floats (offset 7-31)
            "flSurfaceTemp":   vals[o + 7],
            "flTemp":          vals[o + 8],
            "flBrakeTemp":     vals[o + 9],
            "frSurfaceTemp":   vals[o + 10],
            "frTemp":          vals[o + 11],
            "frBrakeTemp":     vals[o + 12],
            "rlSurfaceTemp":   vals[o + 13],
            "rlTemp":          vals[o + 14],
            "rlBrakeTemp":     vals[o + 15],
            "rrSurfaceTemp":   vals[o + 16],
            "rrTemp":          vals[o + 17],
            "rrBrakeTemp":     vals[o + 18],
            "flWear":          vals[o + 19],
            "frWear":          vals[o + 20],
            "rlWear":          vals[o + 21],
            "rrWear":          vals[o + 22],
            "engineTemp":      vals[o + 23],
            "engineWear":      vals[o + 24],
            "gearboxWear":     vals[o + 25],
            "ersWear":         vals[o + 26],
            "charge":          vals[o + 27],
            "energyHarvested": vals[o + 28],
            "energySpent":     vals[o + 29],
            "fuel":            vals[o + 30],
            "fuelDelta":       vals[o + 31],
            # 15 ints (offset 32-46): DriverTelemetry - parte entera
            "teamId":             vals[o + 32],
            "driverNumber":       vals[o + 33],
            "driverId":           vals[o + 34],
            "turnNumber":         vals[o + 35],
            "speed":              vals[o + 36],
            "rpm":                vals[o + 37],
            "gear":               vals[o + 38],
            "position":           vals[o + 39],
            "drsMode":            vals[o + 40],
            "ERSAssist":          vals[o + 41],
            "OvertakeAggression": vals[o + 42],
            "DefendApproach":     vals[o + 43],
            "DriveCleanAir":      vals[o + 44],
            "AvoidHighKerbs":     vals[o + 45],
            "DontFightTeammate":  vals[o + 46],
            # 8 floats (offset 47-54): DriverTelemetry - parte flotante
            "driverBestLap":     vals[o + 47],
            "currentLapTime":    vals[o + 48],
            "lastLapTime":       vals[o + 49],
            "lastS1Time":        vals[o + 50],
            "lastS2Time":        vals[o + 51],
            "lastS3Time":        vals[o + 52],
            "distanceTravelled": vals[o + 53],
            "GapToLeader":       vals[o + 54],
        }
        cars.append(car)

    return {"session": session, "cars": cars}


# ---------------------------------------------------------------------------
# Clase principal de logging
# ---------------------------------------------------------------------------
class F1Logger:
    """Lee el MMF y escribe CSVs de telemetría por piloto y sesión."""

    def __init__(
        self,
        output_root: Path,
        interval:    float,
        driver_filter: Optional[set[int]],
    ) -> None:
        self.output_root   = output_root
        self.interval      = interval
        self.driver_filter = driver_filter  # None = todos los pilotos
        self._running      = False

        # Estado de la sesión activa
        self._session_key: Optional[tuple[int, int]] = None  # (trackId, sessionType)
        self._session_ts:  Optional[str] = None              # timestamp de inicio
        self._track_name:  str = ""
        self._session_type: str = ""

        # Estado por slot de coche (índice 0-21)
        self._last_compound:   dict[int, int]   = {}   # slot → último compound ID
        self._tire_change_lap: dict[int, int]   = {}   # slot → vuelta del último cambio
        self._best_s1:         dict[int, float] = {}   # slot → mejor S1 del piloto
        self._best_s2:         dict[int, float] = {}
        self._best_s3:         dict[int, float] = {}
        self._best_lap_drv:    dict[int, float] = {}   # slot → mejor vuelta del piloto
        # Mejores tiempos de sesión (todos los pilotos)
        self._best_s1_ses:  float = 0.0
        self._best_s2_ses:  float = 0.0
        self._best_s3_ses:  float = 0.0
        self._best_ses_lap: float = 0.0

        # CSV writers: slot → (file_handle, DictWriter)
        self._writers: dict[int, tuple] = {}
        # Nombres de coche: slot → "TeamName1"/"TeamName2"
        self._car_names: dict[int, str] = {}
        # Nombres de piloto: slot → "Nombre Apellido"
        self._driver_names: dict[int, str] = {}
        # Speed Trap: slot → distancia previa y velocidad máxima registrada
        self._prev_dist:  dict[int, float] = {}   # slot → última distanceTravelled
        self._speed_st:   dict[int, int]   = {}   # slot → SpeedST (km/h)
        # Tabla de compuestos cargada desde tire_map.json
        self._tire_map: dict[int, str] = {}

    # ------------------------------------------------------------------
    # Resolución de nombres
    # ------------------------------------------------------------------
    def _load_tire_map(self) -> None:
        """Recarga tire_map.json si existe."""
        path = self.output_root.parent / "tire_map.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self._tire_map = {int(k): str(v) for k, v in raw.items()}
                print(f"  [tire_map] {len(self._tire_map)} mapeos cargados desde {path.name}")
            except Exception as exc:
                print(f"  [WARN] No se pudo cargar tire_map.json: {exc}")
        else:
            self._tire_map = {}

    def _compound_name(self, compound_id: int) -> str:
        if compound_id in self._tire_map:
            return self._tire_map[compound_id]
        return f"C{compound_id}"

    def _resolve_driver(
        self, slot: int, car: dict
    ) -> tuple[str, str, str, str, str]:
        """Retorna (firstName, lastName, driverCode, teamName, carName)."""
        num = car["driverNumber"]
        info = _ROSTER_2024.get(num)
        if info:
            first, last, code, team = info
        else:
            first = "Driver"
            last  = str(num)
            code  = str(num)
            team  = f"Team{car['teamId']}"

        # carName: TeamShortName + slot (1-indexed dentro del equipo)
        car_name = self._car_names.get(slot, f"Car{slot}")
        return first, last, code, team, car_name

    def _assign_car_names(self, cars: list[dict]) -> None:
        """Construye los nombres de coche (e.g. 'AstonMartin1') para la sesión."""
        team_counter: dict[str, int] = defaultdict(int)
        for slot, car in enumerate(cars):
            if car["driverNumber"] == 0:
                continue
            num  = car["driverNumber"]
            info = _ROSTER_2024.get(num)
            team = info[3] if info else f"Team{car['teamId']}"
            team_short = team.replace(" ", "")
            team_counter[team_short] += 1
            slot_num = team_counter[team_short]
            self._car_names[slot]   = f"{team_short}{slot_num}"
            first, last = (info[0], info[1]) if info else ("Driver", str(num))
            self._driver_names[slot] = f"{first} {last}"

    # ------------------------------------------------------------------
    # Gestión de sesión
    # ------------------------------------------------------------------
    def _session_changed(self, track_id: int, session_type: int) -> bool:
        key = (track_id, session_type)
        return key != self._session_key

    def _start_session(self, track_id: int, session_type: int, cars: list[dict]) -> None:
        self._close_all_writers()

        self._session_key  = (track_id, session_type)
        self._track_name   = TRACK_NAMES.get(track_id, f"Track{track_id}")
        self._session_type = SESSION_TYPES.get(session_type, f"Session{session_type}")
        self._session_ts   = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Resetear estado de stint y tiempos
        self._last_compound   = {}
        self._tire_change_lap = {}
        self._best_s1 = {}
        self._best_s2 = {}
        self._best_s3 = {}
        self._best_lap_drv = {}
        self._best_s1_ses  = 0.0
        self._best_s2_ses  = 0.0
        self._best_s3_ses  = 0.0
        self._best_ses_lap = 0.0
        self._car_names    = {}
        self._driver_names = {}
        self._prev_dist    = {}
        self._speed_st     = {}

        self._assign_car_names(cars)
        self._load_tire_map()

        print(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] "
            f"Nueva sesión: {self._track_name} — {self._session_type}"
        )

    def _get_writer(self, slot: int) -> Optional[tuple]:
        """Devuelve el writer para el slot, creándolo si es necesario."""
        if slot in self._writers:
            return self._writers[slot]

        car_name  = self._car_names.get(slot, f"Car{slot}")
        drv_name  = self._driver_names.get(slot, f"Driver_{slot}")
        track_dir = self._track_name
        sess_dir  = self._session_type
        drv_dir   = drv_name

        out_dir = self.output_root / track_dir / sess_dir / drv_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = (
            f"{self._session_ts}_{car_name}_Telemetry"
            f"_{track_dir}_{sess_dir}.csv"
        )
        filepath = out_dir / filename
        fh = open(filepath, "w", newline="", encoding="utf-8")  # noqa: WPS515
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        self._writers[slot] = (fh, writer)
        print(f"  [+] {filepath}")
        return self._writers[slot]

    def _close_all_writers(self) -> None:
        for fh, _ in self._writers.values():
            try:
                fh.close()
            except Exception:
                pass
        self._writers.clear()

    # ------------------------------------------------------------------
    # Cálculos por muestra
    # ------------------------------------------------------------------
    def _update_stint(self, slot: int, car: dict) -> tuple[str, int]:
        """Actualiza el tracking de neumáticos. Retorna (compound_name, tire_age)."""
        cid = car["tireCompound"]
        lap = car["currentLap"]

        if slot not in self._last_compound or self._last_compound[slot] != cid:
            # Cambio de neumático detectado — guardar como 1-indexed (igual que el plugin original)
            self._last_compound[slot]   = cid
            self._tire_change_lap[slot] = lap + 1

        change_lap = self._tire_change_lap.get(slot, 0)
        tire_age   = max(0, (lap + 1) - change_lap)
        return self._compound_name(cid), tire_age

    def _update_best_times(self, slot: int, car: dict) -> None:
        """Actualiza los mejores tiempos del piloto y de la sesión."""
        def _better(new: float, old: float) -> float:
            if new > 0 and (old == 0 or new < old):
                return new
            return old

        s1 = car["lastS1Time"]
        s2 = car["lastS2Time"]
        s3 = car["lastS3Time"]
        bl = car["driverBestLap"]

        self._best_s1[slot]     = _better(s1, self._best_s1.get(slot, 0.0))
        self._best_s2[slot]     = _better(s2, self._best_s2.get(slot, 0.0))
        self._best_s3[slot]     = _better(s3, self._best_s3.get(slot, 0.0))
        self._best_lap_drv[slot] = _better(bl, self._best_lap_drv.get(slot, 0.0))

        self._best_s1_ses  = _better(s1, self._best_s1_ses)
        self._best_s2_ses  = _better(s2, self._best_s2_ses)
        self._best_s3_ses  = _better(s3, self._best_s3_ses)
        self._best_ses_lap = _better(bl, self._best_ses_lap)

    def _update_speed_trap(self, slot: int, car: dict) -> int:
        """Detecta cuando el coche pasa por el speed trap y guarda la velocidad.

        El speed trap se calcula comparando distanceTravelled con la distancia
        conocida del punto de medición para cada circuito (igual que el plugin
        original).  Retorna la última velocidad registrada en el speed trap.
        """
        dist      = car["distanceTravelled"]
        prev      = self._prev_dist.get(slot, 0.0)
        trap_dist = SPEED_TRAP_DIST.get(self._session_key[0] if self._session_key else 0, 0.0)

        if trap_dist > 0 and prev < trap_dist <= dist:
            # El coche acaba de cruzar el speed trap en esta muestra
            self._speed_st[slot] = car["speed"]

        self._prev_dist[slot] = dist
        return self._speed_st.get(slot, 0)

    @staticmethod
    def _pit_status_label(status: int, session_type: int) -> str:
        """Devuelve la etiqueta correcta del estado de pit.

        En Race/Sprint (sessionType 6 ó 7) el estado 0 es 'On Track'.
        En el resto de sesiones es 'None'.
        """
        if status == 0:
            return "On Track" if session_type in (6, 7) else "None"
        return PIT_STATUSES.get(status, "Unknown")

    def _laps_time_remaining(self, session: dict, cars: list[dict]) -> float:
        """Calcula vueltas (carrera) o segundos (práctica/cali) restantes."""
        st  = session["sessionType"]
        tid = session["trackId"]
        if st in (6, 7):  # Race o Sprint
            total = TRACK_LAPS_SPRINT.get(tid, 0) if st == 7 else TRACK_LAPS.get(tid, 0)
            # Buscar el líder (position == 0 → P1 en indexación 0 del juego)
            leader_lap = 0
            for c in cars:
                if c["position"] == 0 and c["driverNumber"] > 0:
                    leader_lap = c["currentLap"]
                    break
            return float(max(0, total - (leader_lap + 1)))
        else:
            dur_s = SESSION_LENGTH_MIN.get(st, 60) * 60
            return float(max(0.0, dur_s - session["timeElapsed"]))

    def _build_pos_to_name(self, cars: list[dict]) -> dict[int, str]:
        """Mapa posición → nombre de coche."""
        result: dict[int, str] = {}
        for slot, c in enumerate(cars):
            if c["driverNumber"] == 0:
                continue
            pos = c["position"]
            result[pos] = self._car_names.get(slot, f"Car{slot}")
        return result

    def _gap_in_front(self, session: dict, car: dict, cars: list[dict]) -> float:
        pos = car["position"]
        if pos == 0:
            return 0.0
        st = session["sessionType"]
        for c in cars:
            if c["position"] == pos - 1 and c["driverNumber"] > 0:
                if st in (6, 7):
                    return max(0.0, car["GapToLeader"] - c["GapToLeader"])
                else:
                    bl_self = car["driverBestLap"]
                    bl_fwd  = c["driverBestLap"]
                    if bl_self > 0 and bl_fwd > 0:
                        return max(0.0, bl_self - bl_fwd)
        return 0.0

    def _gap_behind(self, session: dict, car: dict, cars: list[dict]) -> float:
        pos = car["position"]
        st  = session["sessionType"]
        for c in cars:
            if c["position"] == pos + 1 and c["driverNumber"] > 0:
                if st in (6, 7):
                    return max(0.0, c["GapToLeader"] - car["GapToLeader"])
                else:
                    bl_self = car["driverBestLap"]
                    bl_beh  = c["driverBestLap"]
                    if bl_self > 0 and bl_beh > 0:
                        return max(0.0, bl_beh - bl_self)
        return 0.0

    # ------------------------------------------------------------------
    # Escritura de una fila CSV
    # ------------------------------------------------------------------
    def _write_row(
        self,
        slot:    int,
        ts:      str,
        session: dict,
        car:     dict,
        cars:    list[dict],
        laps_time_rem: float,
        pos_to_name:   dict[int, str],
    ) -> None:
        result = self._get_writer(slot)
        if result is None:
            return
        _, writer = result

        first, last, code, team, car_name = self._resolve_driver(slot, car)
        compound, tire_age = self._update_stint(slot, car)
        self._update_best_times(slot, car)
        speed_st = self._update_speed_trap(slot, car)

        pos      = car["position"]   # 0-indexed en el MMF
        car_fwd  = pos_to_name.get(pos - 1, "") if pos > 0 else car_name
        car_beh  = pos_to_name.get(pos + 1, "")
        gap_fwd  = self._gap_in_front(session, car, cars)
        gap_beh  = self._gap_behind(session, car, cars)

        row = {
            "timestamp":           ts,
            "trackName":           self._track_name,
            "sessionType":         self._session_type,
            "timeElapsed":         round(session["timeElapsed"], 3),
            "Laps/Time Remaining": round(laps_time_rem, 3),
            "driverNumber":        car["driverNumber"],
            "driverFirstName":     first,
            "driverLastName":      last,
            "driverCode":          code,
            "teamName":            team,
            "pitstopStatus":       self._pit_status_label(car["pitStopStatus"], session["sessionType"]),
            "currentLap":          car["currentLap"] + 1,  # 0-indexed → 1-indexed
            "turnNumber":          car["turnNumber"],
            "distanceTravelled":   round(car["distanceTravelled"], 4),
            "position":            pos + 1,               # 0-indexed → 1-indexed
            "gapToLeader":         round(car["GapToLeader"], 4),
            "carInFront":          car_fwd,
            "gapInFront":          round(gap_fwd, 4),
            "carBehind":           car_beh,
            "gapBehind":           round(gap_beh, 4),
            "compound":            compound,
            "tire_age":            tire_age,
            "flSurfaceTemp":       round(car["flSurfaceTemp"], 4),
            "flTemp":              round(car["flTemp"], 4),
            "flBrakeTemp":         round(car["flBrakeTemp"], 4),
            "frSurfaceTemp":       round(car["frSurfaceTemp"], 4),
            "frTemp":              round(car["frTemp"], 4),
            "frBrakeTemp":         round(car["frBrakeTemp"], 4),
            "rlSurfaceTemp":       round(car["rlSurfaceTemp"], 4),
            "rlTemp":              round(car["rlTemp"], 4),
            "rlBrakeTemp":         round(car["rlBrakeTemp"], 4),
            "rrSurfaceTemp":       round(car["rrSurfaceTemp"], 4),
            "rrTemp":              round(car["rrTemp"], 4),
            "rrBrakeTemp":         round(car["rrBrakeTemp"], 4),
            "flDeg":               round(car["flWear"], 4),
            "frDeg":               round(car["frWear"], 4),
            "rlDeg":               round(car["rlWear"], 4),
            "rrDeg":               round(car["rrWear"], 4),
            "speed":               car["speed"],
            "SpeedST":             speed_st,
            "rpm":                 car["rpm"],
            "gear":                car["gear"],
            "engineTemp":          round(car["engineTemp"], 4),
            "engineDeg":           round(car["engineWear"], 4),
            "gearboxDeg":          round(car["gearboxWear"], 4),
            "ersDeg":              round(car["ersWear"], 4),
            "charge":              round(car["charge"], 4),
            "energyHarvested":     round(car["energyHarvested"], 4),
            "energySpent":         round(car["energySpent"], 4),
            "fuel":                round(car["fuel"], 4),
            "fuelDelta":           round(car["fuelDelta"], 6),
            "paceMode":            PACE_MODES.get(car["paceMode"], str(car["paceMode"])),
            "fuelMode":            FUEL_MODES.get(car["fuelMode"], str(car["fuelMode"])),
            "ersMode":             ERS_MODES.get(car["ersMode"], str(car["ersMode"])),
            "drsMode":             DRS_MODES.get(car["drsMode"], str(car["drsMode"])),
            "ersAssist":           bool(car["ERSAssist"]),
            "driveCleanAir":       bool(car["DriveCleanAir"]),
            "avoidHighKerbs":      bool(car["AvoidHighKerbs"]),
            "dontFightTeammate":   bool(car["DontFightTeammate"]),
            "overtakeAggression":  OVERTAKE_MODES.get(car["OvertakeAggression"], str(car["OvertakeAggression"])),
            "defendApproach":      DEFEND_MODES.get(car["DefendApproach"], str(car["DefendApproach"])),
            "currentLapTime":      round(car["currentLapTime"], 4),
            "driverBestLap":       round(car["driverBestLap"], 4),
            "lastLapTime":         round(car["lastLapTime"], 4),
            "lastS1Time":          round(car["lastS1Time"], 4),
            "driverBestS1Time":    round(self._best_s1.get(slot, 0.0), 4),
            "lastS2Time":          round(car["lastS2Time"], 4),
            "driverBestS2Time":    round(self._best_s2.get(slot, 0.0), 4),
            "lastS3Time":          round(car["lastS3Time"], 4),
            "driverBestS3Time":    round(self._best_s3.get(slot, 0.0), 4),
            "bestSessionTime":     round(self._best_ses_lap, 4),
            "bestS1Time":          round(self._best_s1_ses, 4),
            "bestS2Time":          round(self._best_s2_ses, 4),
            "bestS3Time":          round(self._best_s3_ses, 4),
            "rubber":              round(session["rubber"], 4),
            "airTemp":             round(session["airTemp"], 4),
            "trackTemp":           round(session["trackTemp"], 4),
            "weather":             WEATHER_TYPES.get(session["weather"], f"W{session['weather']}"),
            "waterOnTrack":        round(session["waterOnTrack"], 4),
        }

        writer.writerow(row)

    # ------------------------------------------------------------------
    # Modo prueba (--test)
    # ------------------------------------------------------------------
    def _run_test(self) -> None:
        """Genera datos sintéticos para verificar la exportación CSV.

        No requiere MemoryReader.exe ni el juego en ejecución.
        """
        print(
            "[TEST] Modo prueba activado.\n"
            "  Se generarán 30 muestras para Bahrain Race\n"
            "  con Fernando Alonso (#14) y Lance Stroll (#18).\n"
        )

        _EMPTY: dict = {
            "driverPos": 0, "currentLap": 0, "tireCompound": 2,
            "pitStopStatus": 0, "paceMode": 2, "fuelMode": 1, "ersMode": 0,
            "flSurfaceTemp": 0.0, "flTemp": 0.0, "flBrakeTemp": 0.0,
            "frSurfaceTemp": 0.0, "frTemp": 0.0, "frBrakeTemp": 0.0,
            "rlSurfaceTemp": 0.0, "rlTemp": 0.0, "rlBrakeTemp": 0.0,
            "rrSurfaceTemp": 0.0, "rrTemp": 0.0, "rrBrakeTemp": 0.0,
            "flWear": 1.0, "frWear": 1.0, "rlWear": 1.0, "rrWear": 1.0,
            "engineTemp": 0.0, "engineWear": 1.0, "gearboxWear": 1.0,
            "ersWear": 1.0, "charge": 1.0, "energyHarvested": 0.0,
            "energySpent": 0.0, "fuel": 0.0, "fuelDelta": 0.0,
            "teamId": 0, "driverNumber": 0, "driverId": 0,
            "turnNumber": 5, "speed": 0, "rpm": 0, "gear": 0, "position": 0,
            "drsMode": 0, "ERSAssist": 0, "OvertakeAggression": 1,
            "DefendApproach": 1, "DriveCleanAir": 0, "AvoidHighKerbs": 0,
            "DontFightTeammate": 0,
            "driverBestLap": 0.0, "currentLapTime": 0.0, "lastLapTime": 0.0,
            "lastS1Time": 0.0, "lastS2Time": 0.0, "lastS3Time": 0.0,
            "distanceTravelled": 0.0, "GapToLeader": 0.0,
        }

        cars: list[dict] = [dict(_EMPTY) for _ in range(DRIVER_COUNT)]

        # Slot 0: Alonso — P12 (posición 0-indexed: 11)
        cars[0].update({
            "driverNumber": 14, "position": 11, "currentLap": 4,
            "tireCompound": 2,
            "flSurfaceTemp": 103.9, "flTemp": 105.0, "flBrakeTemp": 355.0,
            "frSurfaceTemp": 103.9, "frTemp": 105.0, "frBrakeTemp": 355.0,
            "rlSurfaceTemp": 103.9, "rlTemp": 105.0, "rlBrakeTemp": 305.0,
            "rrSurfaceTemp": 103.9, "rrTemp": 105.0, "rrBrakeTemp": 305.0,
            "flWear": 0.95, "frWear": 0.95, "rlWear": 0.97, "rrWear": 0.97,
            "engineTemp": 100.9, "engineWear": 0.98, "gearboxWear": 0.99,
            "fuel": 106.5, "fuelDelta": -0.0013,
            "speed": 282, "rpm": 12100, "gear": 7,
            "currentLapTime": 44.8, "distanceTravelled": 155.0, "GapToLeader": 15.3,
        })

        # Slot 1: Stroll — P15 (posición 0-indexed: 14)
        cars[1].update({
            "driverNumber": 18, "position": 14, "currentLap": 4,
            "tireCompound": 2,
            "flSurfaceTemp": 102.1, "flTemp": 103.5, "flBrakeTemp": 342.0,
            "frSurfaceTemp": 102.1, "frTemp": 103.5, "frBrakeTemp": 342.0,
            "rlSurfaceTemp": 102.1, "rlTemp": 103.5, "rlBrakeTemp": 292.0,
            "rrSurfaceTemp": 102.1, "rrTemp": 103.5, "rrBrakeTemp": 292.0,
            "flWear": 0.97, "frWear": 0.97, "rlWear": 0.98, "rrWear": 0.98,
            "engineTemp": 101.0, "engineWear": 0.97, "gearboxWear": 0.99,
            "fuel": 104.8, "fuelDelta": -0.0012,
            "speed": 276, "rpm": 11900, "gear": 7,
            "currentLapTime": 45.6, "distanceTravelled": 141.0, "GapToLeader": 18.9,
        })

        session: dict = {
            "trackId": 2, "sessionType": 6,
            "timeElapsed": 285.0, "rubber": 0.31,
            "airTemp": 26.0, "trackTemp": 32.4,
            "weather": 1, "waterOnTrack": 0.0,
        }

        self._start_session(2, 6, cars)
        # Tabla de compuestos básica para el test (sin tire_map.json)
        self._tire_map = {0: "Hard", 1: "Medium", 2: "Soft", 3: "Intermediates", 4: "Wet"}

        ROWS = 30
        for step in range(ROWS):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            session["timeElapsed"] = round(session["timeElapsed"] + 0.05, 3)
            for c in [cars[0], cars[1]]:
                c["currentLapTime"] = round(c["currentLapTime"] + 0.05, 3)
                c["distanceTravelled"] = round(c["distanceTravelled"] + 5.0, 4)
            ltr       = self._laps_time_remaining(session, cars)
            pos_to_nm = self._build_pos_to_name(cars)
            for slot in [0, 1]:
                self._write_row(slot, ts, session, cars[slot], cars, ltr, pos_to_nm)
            time.sleep(0.02)

        self._close_all_writers()
        print(
            f"\n[TEST] Listo — {ROWS} muestras por piloto escritas en:\n"
            f"  {self.output_root / 'Bahrain' / 'Race'}\n"
        )

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------
    def run(self) -> None:
        self._running = True
        h = ptr = 0
        connected = False

        print(f"[logger] Buscando MMF '{MMF_NAME}'…")
        _idle_ticks  = 0
        _zero_ticks  = 0   # contador de frames con todos los coches a cero

        while self._running:
            # Intentar conectar al MMF
            if not connected:
                try:
                    h, ptr = _mmf_open(MMF_NAME)
                    connected = True
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectado al MMF.")
                except OSError as exc:
                    print(f"  [WAIT] {exc}\n  Reintentando en {DEFAULT_RECONNECT_DELAY}s…")
                    time.sleep(DEFAULT_RECONNECT_DELAY)
                    continue

            # Leer y procesar
            try:
                raw  = _mmf_read(ptr)
                data = _unpack(raw)
                if data is None:
                    time.sleep(self.interval)
                    continue

                session = data["session"]
                cars    = data["cars"]
                tid     = session["trackId"]
                st      = session["sessionType"]

                # Detectar cambio de sesión
                if self._session_changed(tid, st) and tid != 0:
                    self._start_session(tid, st, cars)

                # Saltar si la sesión aún no es válida
                if self._session_key is None or tid == 0:
                    _idle_ticks += 1
                    if _idle_ticks % 200 == 1:
                        track_str = TRACK_NAMES.get(tid, str(tid)) if tid else "menú principal"
                        sess_str  = SESSION_TYPES.get(st, str(st))
                        nums = [c["driverNumber"] for c in cars if c["driverNumber"] != 0]
                        nums_str = str(sorted(set(nums))) if nums else "(ninguno — menú/sin sesión)"
                        print(
                            f"  [esperando] pista={track_str!r}  "
                            f"tipo={sess_str!r}  "
                            f"(trackId={tid}, sessionType={st})\n"
                            f"    driverNumbers en MMF: {nums_str}"
                        )
                    time.sleep(self.interval)
                    continue

                ts_now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                ltr        = self._laps_time_remaining(session, cars)
                pos_to_nm  = self._build_pos_to_name(cars)

                active_slots = [c for c in cars if c["driverNumber"] != 0]
                if not active_slots:
                    # Todos los coches tienen driverNumber=0 → MemoryReader.exe
                    # posiblemente no puede leer el juego (actualización del juego
                    # que invalida las direcciones de memoria hardcodeadas).
                    _zero_ticks += 1
                    if _zero_ticks == 200:
                        print(
                            "\n  [AVISO] MemoryReader.exe está enviando datos vacíos "
                            "(todos los coches con driverNumber=0) tras ~10 s.\n"
                            "  Posibles causas:\n"
                            "  1. El juego no está en una sesión activa (menú principal).\n"
                            "  2. Una actualización del juego ha invalidado los offsets\n"
                            "     de memoria de MemoryReader.exe. Comprueba si hay una\n"
                            "     versión nueva en https://github.com/Asviix/F1Manager2024Logger\n"
                        )
                    time.sleep(self.interval)
                    continue
                _zero_ticks = 0

                for slot, car in enumerate(cars):
                    num = car["driverNumber"]
                    if num == 0:
                        continue  # slot vacío
                    if self.driver_filter and num not in self.driver_filter:
                        continue

                    self._write_row(slot, ts_now, session, car, cars, ltr, pos_to_nm)

                time.sleep(self.interval)

            except OSError:
                # El MMF desapareció (MemoryReader se cerró)
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Conexión perdida. Reconectando…")
                _mmf_close(h, ptr)
                connected = False
                h = ptr = 0

        # Limpieza al salir
        self._close_all_writers()
        if connected and ptr:
            _mmf_close(h, ptr)
        print("\n[logger] Detenido.")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Logger Python para F1 Manager 2024.\n"
            "Lee el MMF 'F1ManagerTelemetry' creado por MemoryReader.exe\n"
            "y exporta CSVs al formato del dashboard f1_pitstop."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--output", "-o",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=(
            f"Directorio raíz de salida. Por defecto: {_DEFAULT_OUTPUT}"
        ),
    )
    p.add_argument(
        "--interval", "-i",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Intervalo de muestreo en segundos (por defecto: {DEFAULT_INTERVAL})",
    )
    p.add_argument(
        "--drivers", "-d",
        type=int,
        nargs="+",
        default=[14, 18],   # Aston Martin: Alonso #14, Stroll #18
        help=(
            "Filtrar por número(s) de piloto.  Ej: --drivers 14 18\n"
            "Por defecto: 14 (Alonso) y 18 (Stroll) — Aston Martin.\n"
            "Usa --drivers 0 para registrar todos los pilotos activos."
        ),
    )
    p.add_argument(
        "--test",
        action="store_true",
        help=(
            "Modo prueba: genera CSVs con datos sintéticos sin necesitar\n"
            "MemoryReader.exe ni el juego. Útil para verificar la instalación."
        ),
    )
    return p.parse_args()


def main() -> None:
    # Verificar tamaño del struct en tiempo de carga
    expected = 4880
    if TELEMETRY_SIZE != expected:
        raise SystemExit(
            f"[ERROR] Tamaño del struct inesperado: {TELEMETRY_SIZE} bytes "
            f"(se esperaban {expected}).  Revisa STRUCT_FORMAT."
        )

    args = _parse_args()

    driver_filter: Optional[set[int]] = None
    if args.drivers and args.drivers != [0]:
        driver_filter = set(args.drivers)
        print(f"[logger] Filtrando pilotos: {sorted(driver_filter)}")

    logger = F1Logger(
        output_root=args.output,
        interval=args.interval,
        driver_filter=driver_filter,
    )

    # Capturar Ctrl+C para cierre limpio
    def _stop(sig, frame):  # noqa: ANN001,ANN002
        print("\n[logger] Señal de parada recibida…")
        logger._running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if args.test:
        logger._run_test()
        return

    print(
        f"[logger] F1 Pitstop — Logger sin SimHub\n"
        f"  Salida : {args.output}\n"
        f"  Polling: {args.interval * 1000:.0f} ms\n"
        f"  Ctrl+C para detener.\n"
    )

    logger.run()


if __name__ == "__main__":
    import traceback as _tb
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        _tb.print_exc()
        raise SystemExit(1)
