"""Tests for f1m.modeling — degradation model fitting and lap-time utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from f1m.modeling import (
    adjust_lap_time_for_conditions,
    fit_degradation_model,
    max_stint_length,
    stint_time,
)

# ---------------------------------------------------------------------------
# stint_time
# ---------------------------------------------------------------------------

class TestStintTime:
    def test_zero_laps(self):
        assert stint_time(90.0, 0.15, 0) == pytest.approx(0.0)

    def test_one_lap(self):
        # 1 lap: intercept * 1 + slope * 0 * 1 / 2 = intercept
        assert stint_time(90.0, 0.15, 1) == pytest.approx(90.0)

    def test_two_laps(self):
        # 2 laps: 2 * 90 + 0.15 * 1 * 2 / 2 = 180 + 0.15 = 180.15
        assert stint_time(90.0, 0.15, 2) == pytest.approx(180.15)

    def test_positive_slope_increases_time(self):
        t_flat  = stint_time(90.0, 0.0,  10)
        t_slope = stint_time(90.0, 0.15, 10)
        assert t_slope > t_flat

    def test_negative_laps_returns_zero(self):
        assert stint_time(90.0, 0.15, -1) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# adjust_lap_time_for_conditions
# ---------------------------------------------------------------------------

class TestAdjustLapTimeForConditions:
    def test_no_conditions_unchanged(self):
        assert adjust_lap_time_for_conditions(90.0) == pytest.approx(90.0)

    def test_safety_car_increases_time(self):
        t = adjust_lap_time_for_conditions(90.0, safety_car=True)
        assert t > 90.0

    def test_rain_increases_time(self):
        t = adjust_lap_time_for_conditions(90.0, rain=True)
        assert t > 90.0

    def test_both_conditions_stack(self):
        t_sc   = adjust_lap_time_for_conditions(90.0, safety_car=True)
        t_both = adjust_lap_time_for_conditions(90.0, safety_car=True, rain=True)
        assert t_both > t_sc


# ---------------------------------------------------------------------------
# fit_degradation_model
# ---------------------------------------------------------------------------

class TestFitDegradationModel:
    def test_empty_dataframe_returns_empty_dict(self):
        result = fit_degradation_model(pd.DataFrame())
        assert result == {}

    def test_returns_dict(self, multi_compound_laps):
        result = fit_degradation_model(multi_compound_laps)
        assert isinstance(result, dict)

    def test_all_three_compounds_fitted(self, multi_compound_laps):
        result = fit_degradation_model(multi_compound_laps)
        assert "Soft" in result
        assert "Medium" in result
        assert "Hard" in result

    def test_coefficients_are_tuples(self, multi_compound_laps):
        result = fit_degradation_model(multi_compound_laps)
        for comp, coeffs in result.items():
            assert isinstance(coeffs, tuple), f"{comp} coefficients not a tuple"

    def test_intercept_physically_realistic(self, multi_compound_laps):
        result = fit_degradation_model(multi_compound_laps)
        for comp, coeffs in result.items():
            if len(coeffs) == 2:
                # 2-param: (intercept, slope) — intercept must be a realistic lap time
                a = coeffs[0]
                assert 55.0 <= a <= 220.0, f"{comp} 2-param intercept {a} out of F1 range"

    def test_slope_physically_realistic(self, multi_compound_laps):
        result = fit_degradation_model(multi_compound_laps)
        for comp, coeffs in result.items():
            b = coeffs[1]
            assert -1.0 <= b <= 10.0, f"{comp} slope {b} out of range"

    def test_soft_degradation_higher_than_hard(self, multi_compound_laps):
        result = fit_degradation_model(multi_compound_laps)
        if "Soft" in result and "Hard" in result:
            assert result["Soft"][1] >= result["Hard"][1]

    def test_single_compound_works(self, soft_laps):
        result = fit_degradation_model(soft_laps)
        assert "Soft" in result

    def test_insufficient_data_excluded(self):
        # Only 2 rows — below the 5-row threshold
        df = pd.DataFrame(
            {
                "compound": ["Soft", "Soft"],
                "tire_age": [1, 2],
                "lap_time_s": [90.0, 90.3],
                "session": ["Practice 1", "Practice 1"],
            }
        )
        result = fit_degradation_model(df)
        assert "Soft" not in result

    def test_c_notation_merged(self):
        """C3 and C4 should be merged into the same canonical compound."""

        np.random.seed(42)
        rows = []
        for lap in range(1, 21):
            rows.append(
                {
                    "compound": "C3" if lap <= 10 else "C4",
                    "tire_age": lap - 1 if lap <= 10 else lap - 11,
                    "lap_time_s": 90.0 + 0.15 * (lap - 1 if lap <= 10 else lap - 11)
                    + np.random.normal(0, 0.05),
                    "session": "Practice 1",
                }
            )
        df = pd.DataFrame(rows)
        result = fit_degradation_model(df)
        # Both C3 and C4 map to the same canonical label — only one key expected
        assert len(result) == 1


# ---------------------------------------------------------------------------
# max_stint_length
# ---------------------------------------------------------------------------

class TestMaxStintLength:
    def test_returns_positive_int(self, multi_compound_laps):
        result = max_stint_length(multi_compound_laps, "Soft")
        assert isinstance(result, int)
        assert result > 0

    def test_empty_data_returns_default(self):
        result = max_stint_length(pd.DataFrame(), "Soft")
        assert isinstance(result, int)
        assert result > 0

    def test_unknown_compound_returns_default(self, multi_compound_laps):
        result = max_stint_length(multi_compound_laps, "Wet")
        assert isinstance(result, int)
        assert result > 0
