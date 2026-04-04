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

# Temperature model parameters
# Compound display labels: map raw compound name → enriched display label.
# Covers both Pirelli spec IDs (C1–C5) and plain category names.
# Any unknown compound (e.g. custom labels) is shown as-is by the helper.
COMPOUND_DISPLAY_MAP: dict[str, str] = {
    # Plain category names – passthrough with consistent casing
    "Hard": "Hard",
    "Medium": "Medium",
    "Soft": "Soft",
    "Intermediates": "Inter",
    "Wet": "Wet",
    # Pirelli numerical spec IDs with category hint
    "C1": "C1 · Hard",
    "C2": "C2 · Medium",
    "C3": "C3 · Soft",
    "C4": "C4 · Soft",
    "C5": "C5 · Soft",
    # Game-specific compound IDs (fallback when tire_map.json not loaded)
    "C10": "C10 · Hard",
    "C12": "C12 · Medium",
}

# F1-standard compound colors (Plotly hex strings).
# Used as color_discrete_map in charts.
COMPOUND_COLOR_MAP: dict[str, str] = {
    "Hard": "#C8C8C8",         # Silver-white
    "Medium": "#FFD700",       # Yellow
    "Soft": "#E8002D",         # Pirelli red
    "Intermediates": "#39B54A",  # Green
    "Inter": "#39B54A",
    "Wet": "#0067FF",          # Blue
    # Pirelli spec IDs – same palette as category
    "C1": "#C8C8C8",
    "C2": "#FFD700",
    "C3": "#E8002D",
    "C4": "#E8002D",
    "C5": "#E8002D",
    # Game-specific compound IDs
    "C10": "#C8C8C8",
    "C12": "#FFD700",
    # Enriched labels produced by display_compound()
    "C1 · Hard": "#C8C8C8",
    "C2 · Medium": "#FFD700",
    "C3 · Soft": "#E8002D",
    "C4 · Soft": "#E8002D",
    "C5 · Soft": "#E8002D",
    "C10 · Hard": "#C8C8C8",
    "C12 · Medium": "#FFD700",
}

# Canonical compound map: normalises any raw compound name → canonical hardness
# category used internally by the degradation model and planner.
# Two different Soft specs (e.g. C3 and C4) must be merged into "Soft" so the
# regression has enough data and so the planner treats them as one strategy
# option.
COMPOUND_CANONICAL_MAP: dict[str, str] = {
    # Plain category names – passthrough
    "Hard": "Hard",
    "Medium": "Medium",
    "Soft": "Soft",
    "Intermediates": "Intermediates",
    "Inter": "Intermediates",
    "Wet": "Wet",
    # Pirelli numerical spec IDs → hardness category
    "C1": "Hard",
    "C2": "Medium",
    "C3": "Soft",
    "C4": "Soft",
    "C5": "Soft",
    # Game-specific IDs
    "C10": "Hard",
    "C11": "Medium",
    "C12": "Medium",
    "C13": "Soft",
    "C14": "Soft",
    "C15": "Soft",
    # Enriched display labels produced by display_compound()
    "C1 · Hard": "Hard",
    "C2 · Medium": "Medium",
    "C3 · Soft": "Soft",
    "C4 · Soft": "Soft",
    "C5 · Soft": "Soft",
    "C10 · Hard": "Hard",
    "C12 · Medium": "Medium",
}

TEMP_REF_CELSIUS = 40.0  # reference track temp (°C) baked into the 4-param intercept
MIN_TEMP_STD = 2.0  # minimum trackTemp std-dev (°C) to activate the temperature coefficient
