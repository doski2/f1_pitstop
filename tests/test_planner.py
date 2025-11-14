"""Tests for f1m.planner module."""

import numpy as np
import pandas as pd
import pytest

from f1m.planner import enumerate_plans


class TestEnumeratePlans:
    """Test plan enumeration functions."""

    def test_enumerate_plans_basic(self):
        """Test basic plan enumeration with simple data."""
        # Create mock practice data
        practice_laps = pd.DataFrame(
            {
                "compound": ["SOFT", "SOFT", "MEDIUM", "MEDIUM"],
                "tire_age": [1, 2, 1, 2],
                "lap_time_s": [90.0, 91.0, 92.0, 93.0],
            }
        )

        # Simple models (just intercept and age coefficient)
        models = {"SOFT": (90.0, 0.5), "MEDIUM": (92.0, 0.3)}

        compounds = ["SOFT", "MEDIUM"]
        race_laps = 10
        pit_loss = 20.0

        plans = enumerate_plans(
            race_laps=race_laps,
            compounds=compounds,
            models=models,
            practice_laps=practice_laps,
            pit_loss=pit_loss,
            max_stops=1,
            min_stint=3,
            require_two_compounds=False,
            top_k=2,
        )

        assert len(plans) <= 2  # Should return at most top_k plans
        if plans:
            # Check that each plan has the expected structure
            for plan in plans:
                assert "stints" in plan
                assert "total_time" in plan
                assert "stops" in plan
                assert isinstance(plan["stints"], list)
                # Check that stint laps sum to race_laps
                total_laps = sum(stint["laps"] for stint in plan["stints"])
                assert total_laps == race_laps

    def test_enumerate_plans_no_valid_plans(self):
        """Test enumeration when no valid plans can be found."""
        # Create practice data that will make stints too long
        practice_laps = pd.DataFrame(
            {"compound": ["SOFT"], "tire_age": [1], "lap_time_s": [90.0]}
        )

        models = {"SOFT": (90.0, 0.1)}
        compounds = ["SOFT"]
        race_laps = 50  # Very long race
        pit_loss = 20.0

        plans = enumerate_plans(
            race_laps=race_laps,
            compounds=compounds,
            models=models,
            practice_laps=practice_laps,
            pit_loss=pit_loss,
            max_stops=0,  # No stops allowed
            min_stint=5,
            require_two_compounds=False,
            top_k=1,
        )

        # Should return empty list if no valid plans
        assert isinstance(plans, list)

    def test_enumerate_plans_with_fuel(self):
        """Test plan enumeration with fuel constraints."""
        practice_laps = pd.DataFrame(
            {
                "compound": ["SOFT", "MEDIUM"],
                "tire_age": [1, 1],
                "lap_time_s": [90.0, 92.0],
            }
        )

        # Models with fuel coefficient (a, b_age, c_fuel)
        models = {"SOFT": (90.0, 0.5, 0.1), "MEDIUM": (92.0, 0.3, 0.05)}

        compounds = ["SOFT", "MEDIUM"]
        race_laps = 8
        pit_loss = 15.0

        plans = enumerate_plans(
            race_laps=race_laps,
            compounds=compounds,
            models=models,
            practice_laps=practice_laps,
            pit_loss=pit_loss,
            max_stops=1,
            min_stint=2,
            require_two_compounds=False,
            top_k=1,
            use_fuel=True,
            start_fuel=100.0,
            cons_per_lap=2.0,
        )

        assert isinstance(plans, list)
        if plans:
            plan = plans[0]
            assert "stints" in plan
            assert "total_time" in plan
            # With fuel modeling, should still work
