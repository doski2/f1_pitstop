"""Tests for f1m.modeling module."""

import numpy as np
import pandas as pd
import pytest

from f1m.modeling import (
    adjust_lap_time_for_conditions,
    fit_degradation_model,
    max_stint_length,
    stint_time,
)


class TestModelingFunctions:
    """Test modeling and degradation functions."""

    def test_fit_degradation_model(self):
        """Test fitting a degradation model from practice data."""
        # Create sample practice data with compound column
        practice_data = pd.DataFrame(
            {
                "compound": ["SOFT"] * 5,
                "tire_age": [1, 2, 3, 4, 5],
                "lap_time_s": [90.0, 90.5, 91.2, 92.1, 93.5],
            }
        )

        model = fit_degradation_model(practice_data)

        assert isinstance(model, dict)
        assert "SOFT" in model
        # Check that it's a reasonable fit
        soft_model = model["SOFT"]
        assert isinstance(soft_model, tuple)
        assert len(soft_model) >= 2

    def test_stint_time(self):
        """Test calculating stint time with intercept and slope."""
        intercept = 90.0
        slope = 0.5
        laps = 5

        time = stint_time(intercept, slope, laps)

        assert isinstance(time, float)
        assert time > 0
        # For 5 laps: 5 * 90 + 0.5 * (5-1) * 5 / 2 = 450 + 0.5 * 4 * 2.5 = 450 + 5 = 455
        expected = laps * intercept + slope * (laps - 1) * laps / 2.0
        assert abs(time - expected) < 1e-6

    def test_max_stint_length(self):
        """Test calculating maximum stint length."""
        # Create practice data with compound column and increasing lap times
        practice_data = pd.DataFrame(
            {
                "compound": ["SOFT"] * 20,
                "tire_age": list(range(1, 21)),  # 20 laps
                "lap_time_s": [90 + 0.5 * i for i in range(20)],  # degrading tires
            }
        )

        max_length = max_stint_length(practice_data, "SOFT")

        assert isinstance(max_length, int)
        assert max_length > 0
        assert max_length <= 22  # max_age + 2 = 20 + 2 = 22

    def test_max_stint_length_insufficient_data(self):
        """Test max stint length with insufficient data."""
        # Very little data
        practice_data = pd.DataFrame(
            {
                "compound": ["SOFT", "SOFT"],
                "tire_age": [1, 2],
                "lap_time_s": [90.0, 90.5],
            }
        )

        max_length = max_stint_length(practice_data, "SOFT")

        assert isinstance(max_length, int)
        assert max_length >= 1  # Should have some minimum


class TestAdjustLapTimeForConditions:
    """Test lap time adjustment functions."""

    def test_no_conditions(self):
        """Test no adjustment when no special conditions."""
        base_time = 90.0
        adjusted = adjust_lap_time_for_conditions(base_time)
        assert adjusted == base_time

    def test_safety_car_only(self):
        """Test adjustment with Safety Car only."""
        base_time = 90.0
        adjusted = adjust_lap_time_for_conditions(base_time, safety_car=True)
        expected = base_time * 1.5  # SAFETY_CAR_TIME_MULTIPLIER
        assert adjusted == expected

    def test_rain_only(self):
        """Test adjustment with rain only."""
        base_time = 90.0
        adjusted = adjust_lap_time_for_conditions(base_time, rain=True)
        expected = base_time * 1.3  # RAIN_TIME_MULTIPLIER
        assert adjusted == expected

    def test_both_conditions(self):
        """Test adjustment with both Safety Car and rain."""
        base_time = 90.0
        adjusted = adjust_lap_time_for_conditions(base_time, safety_car=True, rain=True)
        expected = base_time * 1.5 * 1.3  # Both multipliers
        assert adjusted == pytest.approx(expected)

    def test_zero_base_time(self):
        """Test adjustment with zero base time."""
        base_time = 0.0
        adjusted = adjust_lap_time_for_conditions(base_time, safety_car=True, rain=True)
        assert adjusted == 0.0

    def test_negative_base_time(self):
        """Test adjustment with negative base time (edge case)."""
        base_time = -10.0
        adjusted = adjust_lap_time_for_conditions(base_time, safety_car=True)
        expected = base_time * 1.5
        assert adjusted == expected
