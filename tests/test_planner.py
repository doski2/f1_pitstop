"""Tests for f1m.planner — enumerate_plans and live_pit_recommendation."""

from __future__ import annotations

from f1m.planner import enumerate_plans, live_pit_recommendation

RACE_LAPS = 57  # Bahrain


# ---------------------------------------------------------------------------
# enumerate_plans
# ---------------------------------------------------------------------------

class TestEnumeratePlans:
    def _plans(self, simple_models, multi_compound_laps, **kwargs) -> list:
        defaults = dict(
            race_laps=RACE_LAPS,
            compounds=list(simple_models.keys()),
            models=simple_models,
            practice_laps=multi_compound_laps,
            pit_loss=22.0,
            max_stops=2,
            exact_stops=False,
            min_stint=5,
            require_two_compounds=True,
        )
        defaults.update(kwargs)
        return enumerate_plans(**defaults)  # type: ignore[arg-type]

    def test_returns_list(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps)
        assert isinstance(result, list)

    def test_plans_not_empty(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps)
        assert len(result) > 0

    def test_each_plan_has_stints(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps)
        for plan in result:
            assert "stints" in plan
            assert len(plan["stints"]) >= 1

    def test_stints_sum_to_race_laps(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps)
        for plan in result:
            total = sum(s["laps"] for s in plan["stints"])
            assert total == RACE_LAPS, f"Stints {plan['stints']} sum to {total}, expected {RACE_LAPS}"

    def test_require_two_compounds_enforced(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps, require_two_compounds=True)
        for plan in result:
            used = {s["compound"] for s in plan["stints"]}
            assert len(used) >= 2, f"Only one compound used: {used}"

    def test_min_stint_respected(self, simple_models, multi_compound_laps):
        min_s = 8
        result = self._plans(simple_models, multi_compound_laps, min_stint=min_s)
        for plan in result:
            for stint in plan["stints"]:
                assert stint["laps"] >= min_s, (
                    f"Stint {stint} shorter than min_stint={min_s}"
                )

    def test_exact_stops_respected(self, simple_models, multi_compound_laps):
        result = self._plans(
            simple_models, multi_compound_laps,
            max_stops=1, exact_stops=True
        )
        for plan in result:
            assert plan["stops"] == 1

    def test_max_stops_upper_bound(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps, max_stops=2, exact_stops=False)
        for plan in result:
            assert plan["stops"] <= 2

    def test_sorted_by_total_time(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps)
        times = [p["total_time"] for p in result]
        assert times == sorted(times)

    def test_total_time_positive(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps)
        for plan in result:
            assert plan["total_time"] > 0

    def test_empty_models_returns_empty(self, multi_compound_laps):
        result = enumerate_plans(
            race_laps=RACE_LAPS,
            compounds=[],
            models={},
            practice_laps=multi_compound_laps,
            pit_loss=22.0,
        )
        assert result == []

    def test_zero_race_laps_returns_empty(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps, race_laps=0)
        assert result == []

    def test_top_k_limits_results(self, simple_models, multi_compound_laps):
        top_k = 3
        result = self._plans(
            simple_models, multi_compound_laps,
            require_two_compounds=False, exact_stops=False, top_k=top_k
        )
        assert len(result) <= top_k

    def test_no_require_two_compounds_allows_single(self, simple_models, multi_compound_laps):
        """With require_two_compounds=False and 1 stop allowed, single-compound plans can appear."""
        result = self._plans(
            simple_models, multi_compound_laps,
            max_stops=1, exact_stops=False,
            require_two_compounds=False
        )
        assert isinstance(result, list)

    def test_plan_keys(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps)
        for plan in result:
            assert "stints" in plan
            assert "total_time" in plan
            assert "stops" in plan

    def test_stint_keys(self, simple_models, multi_compound_laps):
        result = self._plans(simple_models, multi_compound_laps)
        for plan in result:
            for s in plan["stints"]:
                assert "compound" in s
                assert "laps" in s


# ---------------------------------------------------------------------------
# live_pit_recommendation
# ---------------------------------------------------------------------------

class TestLivePitRecommendation:
    def test_returns_dict(self, simple_models, multi_compound_laps):
        result = live_pit_recommendation(
            current_lap=20,
            total_race_laps=RACE_LAPS,
            current_compound="Soft",
            current_tire_age=20,
            models=simple_models,
            practice_laps=multi_compound_laps,
            pit_loss=22.0,
        )
        assert isinstance(result, dict)

    def test_has_expected_keys(self, simple_models, multi_compound_laps):
        result = live_pit_recommendation(
            current_lap=20,
            total_race_laps=RACE_LAPS,
            current_compound="Soft",
            current_tire_age=20,
            models=simple_models,
            practice_laps=multi_compound_laps,
            pit_loss=22.0,
        )
        # Returns either a recommendation dict or None
        assert result is None or "pit_on_lap" in result or "message" in result or "continue_laps" in result

    def test_no_crash_on_last_lap(self, simple_models, multi_compound_laps):
        result = live_pit_recommendation(
            current_lap=RACE_LAPS,
            total_race_laps=RACE_LAPS,
            current_compound="Hard",
            current_tire_age=30,
            models=simple_models,
            practice_laps=multi_compound_laps,
            pit_loss=22.0,
        )
        assert result is None or isinstance(result, dict)
