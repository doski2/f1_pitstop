"""Common imports and utilities for the f1m package.

This module provides centralized imports to reduce redundancy across the package.
"""

from __future__ import annotations

# Standard library imports
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple, Union

# Third-party imports
import numpy as np
import pandas as pd

# Package imports
from .constants import (
    COMPOUND_CANONICAL_MAP,
    COMPOUND_COLOR_MAP,
    COMPOUND_DISPLAY_MAP,
    DEFAULT_CONS_PER_LAP,
    DEFAULT_MAX_STOPS,
    DEFAULT_MIN_STINT,
    DEFAULT_PIT_LOSS_SECONDS,
    DEFAULT_START_FUEL,
    DEFAULT_TOP_K_PLANS,
    DRY_CONDITIONS,
    MIN_RUBBER_STD,
    MIN_TEMP_STD,
    RAIN_FLAG,
    RAIN_TIME_MULTIPLIER,
    SAFETY_CAR_FLAG,
    SAFETY_CAR_TIME_MULTIPLIER,
    TEMP_REF_CELSIUS,
    WEAR_CLIFF,
    WET_CONDITIONS,
)
from .telemetry import (
    COL_AVG_WEAR,
    COL_PACE_MODE,
    COL_RAIN,
    COL_RUBBER,
    COL_SAFETY_CAR,
    optimize_dataframe_memory,
)

__all__ = [
    # Standard library
    "Path",
    "Dict",
    "List",
    "Mapping",
    "Optional",
    "Tuple",
    "Union",
    # Third-party
    "np",
    "pd",
    # Package constants
    "DEFAULT_CONS_PER_LAP",
    "DEFAULT_MAX_STOPS",
    "DEFAULT_MIN_STINT",
    "DEFAULT_PIT_LOSS_SECONDS",
    "DEFAULT_START_FUEL",
    "DEFAULT_TOP_K_PLANS",
    "DRY_CONDITIONS",
    "RAIN_FLAG",
    "RAIN_TIME_MULTIPLIER",
    "SAFETY_CAR_FLAG",
    "SAFETY_CAR_TIME_MULTIPLIER",
    "MIN_RUBBER_STD",
    "MIN_TEMP_STD",
    "TEMP_REF_CELSIUS",
    "WEAR_CLIFF",
    "COMPOUND_CANONICAL_MAP",
    "COMPOUND_COLOR_MAP",
    "COMPOUND_DISPLAY_MAP",
    "WET_CONDITIONS",
    # Column constants
    "COL_AVG_WEAR",
    "COL_PACE_MODE",
    "COL_RAIN",
    "COL_RUBBER",
    "COL_SAFETY_CAR",
    # Package utilities
    "optimize_dataframe_memory",
]
