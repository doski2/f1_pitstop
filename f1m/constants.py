"""Constants for the f1m package.

Centralized constants to avoid magic numbers and improve maintainability.
"""

from __future__ import annotations

# Default planning parameters
DEFAULT_MAX_STOPS = 2
DEFAULT_MIN_STINT = 5
DEFAULT_TOP_K_PLANS = 3

# Default fuel parameters
DEFAULT_START_FUEL = 0.0
DEFAULT_CONS_PER_LAP = 0.0

# Pit stop parameters
DEFAULT_PIT_LOSS_SECONDS = 20.0

# Safety Car and Weather flags
SAFETY_CAR_FLAG = "safety_car"
RAIN_FLAG = "rain"
DRY_CONDITIONS = "dry"
WET_CONDITIONS = "wet"

# Default weather impact factors
SAFETY_CAR_TIME_MULTIPLIER = 1.5  # Safety car laps are ~50% slower
RAIN_TIME_MULTIPLIER = 1.3  # Rain laps are ~30% slower
