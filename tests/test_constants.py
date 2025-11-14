"""Tests for f1m.constants module."""

import pytest

from f1m.constants import (
    DEFAULT_CONS_PER_LAP,
    DEFAULT_MAX_STOPS,
    DEFAULT_MIN_STINT,
    DEFAULT_PIT_LOSS_SECONDS,
    DEFAULT_START_FUEL,
    DEFAULT_TOP_K_PLANS,
    INT16_THRESHOLD,
    INT32_THRESHOLD,
    INT64_THRESHOLD,
    MAX_MODEL_MAE,
    MIN_MODEL_R2,
    PERFORMANCE_CRITICAL_THRESHOLD,
    PERFORMANCE_WARNING_THRESHOLD,
    RAIN_TIME_MULTIPLIER,
    SAFETY_CAR_TIME_MULTIPLIER,
)


class TestConstants:
    """Test constants definitions."""

    def test_default_planning_parameters(self):
        """Test default planning parameter values."""
        assert DEFAULT_MAX_STOPS == 2
        assert DEFAULT_MIN_STINT == 5
        assert DEFAULT_TOP_K_PLANS == 3

    def test_default_fuel_parameters(self):
        """Test default fuel parameter values."""
        assert DEFAULT_START_FUEL == 0.0
        assert DEFAULT_CONS_PER_LAP == 0.0

    def test_default_pit_parameters(self):
        """Test default pit stop parameters."""
        assert DEFAULT_PIT_LOSS_SECONDS == 20.0

    def test_memory_optimization_thresholds(self):
        """Test memory optimization threshold constants."""
        assert INT64_THRESHOLD == 2**31 - 1  # Max int32 value
        assert INT32_THRESHOLD == 2**15 - 1  # Max int16 value
        assert INT16_THRESHOLD == 2**7 - 1  # Max int8 value

    def test_performance_thresholds(self):
        """Test performance threshold constants."""
        assert PERFORMANCE_WARNING_THRESHOLD == 1.0
        assert PERFORMANCE_CRITICAL_THRESHOLD == 5.0

    def test_safety_car_constants(self):
        """Test Safety Car related constants."""
        assert SAFETY_CAR_TIME_MULTIPLIER == 1.5
        assert SAFETY_CAR_TIME_MULTIPLIER > 1.0  # Should slow down times

    def test_rain_constants(self):
        """Test rain related constants."""
        assert RAIN_TIME_MULTIPLIER == 1.3
        assert RAIN_TIME_MULTIPLIER > 1.0  # Should slow down times
