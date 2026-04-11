"""Tests for f1m.telemetry — CSV loading, pit detection, lap summary, stint building."""

from __future__ import annotations

import pandas as pd
import pytest

from f1m.telemetry import (
    _parse_lap_time_to_seconds,
    build_lap_summary,
    build_stints,
    detect_pit_events,
    load_multi_session_csvs,
    load_session_csv,
    optimize_dataframe_memory,
)

# ---------------------------------------------------------------------------
# optimize_dataframe_memory
# ---------------------------------------------------------------------------

class TestOptimizeDataframeMemory:
    def test_empty_returns_empty(self):
        result = optimize_dataframe_memory(pd.DataFrame())
        assert result.empty

    def test_int64_downcast_to_int8(self):
        df = pd.DataFrame({"x": pd.array([1, 2, 3], dtype="int64")})
        out = optimize_dataframe_memory(df)
        assert out["x"].dtype == "int8"

    def test_float64_downcast_to_float32(self):
        df = pd.DataFrame({"x": pd.array([1.0, 2.0, 3.0], dtype="float64")})
        out = optimize_dataframe_memory(df)
        assert out["x"].dtype == "float32"

    def test_large_int_stays_int32(self):
        df = pd.DataFrame({"x": pd.array([100_000, 200_000], dtype="int64")})
        out = optimize_dataframe_memory(df)
        assert out["x"].dtype == "int32"

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"x": pd.array([1, 2, 3], dtype="int64")})
        optimize_dataframe_memory(df)
        assert df["x"].dtype == "int64"


# ---------------------------------------------------------------------------
# _parse_lap_time_to_seconds
# ---------------------------------------------------------------------------

class TestParseLapTimeToSeconds:
    def test_float_passthrough(self):
        assert _parse_lap_time_to_seconds(90.5) == pytest.approx(90.5)

    def test_int_passthrough(self):
        assert _parse_lap_time_to_seconds(90) == pytest.approx(90.0)

    def test_mm_ss_string(self):
        assert _parse_lap_time_to_seconds("1:30.5") == pytest.approx(90.5)

    def test_seconds_only_string(self):
        assert _parse_lap_time_to_seconds("90.5") == pytest.approx(90.5)

    def test_none_returns_none(self):
        assert _parse_lap_time_to_seconds(None) is None

    def test_nan_returns_none(self):
        assert _parse_lap_time_to_seconds(float("nan")) is None

    def test_garbage_returns_none(self):
        assert _parse_lap_time_to_seconds("abc") is None


# ---------------------------------------------------------------------------
# load_session_csv
# ---------------------------------------------------------------------------

class TestLoadSessionCsv:
    def test_loads_single_file(self, single_csv_dir):
        csv = next(single_csv_dir.glob("*.csv"))
        df = load_session_csv(csv)
        assert not df.empty
        assert "currentLap" in df.columns

    def test_timestamp_converted_to_datetime(self, single_csv_dir):
        csv = next(single_csv_dir.glob("*.csv"))
        df = load_session_csv(csv)
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

    def test_sorted_by_timestamp(self, single_csv_dir):
        csv = next(single_csv_dir.glob("*.csv"))
        df = load_session_csv(csv)
        assert df["timestamp"].is_monotonic_increasing

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(Exception):
            load_session_csv(tmp_path / "nonexistent.csv")


# ---------------------------------------------------------------------------
# load_multi_session_csvs
# ---------------------------------------------------------------------------

class TestLoadMultiSessionCsvs:
    def test_empty_dir_returns_empty(self, tmp_path):
        df = load_multi_session_csvs(tmp_path)
        assert df.empty

    def test_single_file_returns_same_as_load_session_csv(self, single_csv_dir):
        df_multi = load_multi_session_csvs(single_csv_dir)
        df_single = load_session_csv(next(single_csv_dir.glob("*.csv")))
        assert len(df_multi) == len(df_single)

    def test_two_files_merged_all_laps(self, multi_csv_dir):
        df = load_multi_session_csvs(multi_csv_dir)
        assert df["currentLap"].max() == 20

    def test_two_files_row_count(self, multi_csv_dir):
        df = load_multi_session_csvs(multi_csv_dir)
        # 10 rows per file, no overlap
        assert len(df) == 20

    def test_overlapping_files_deduplicates(self, overlapping_csv_dir):
        df = load_multi_session_csvs(overlapping_csv_dir)
        # 20 unique timestamps even though 3 rows were duplicated
        assert len(df) == 20

    def test_result_sorted_by_timestamp(self, multi_csv_dir):
        df = load_multi_session_csvs(multi_csv_dir)
        assert df["timestamp"].is_monotonic_increasing


# ---------------------------------------------------------------------------
# detect_pit_events
# ---------------------------------------------------------------------------

class TestDetectPitEvents:
    def _base_df(self) -> pd.DataFrame:
        """10-lap stint, no pits. tire_age starts at 2 to avoid first-row false positive."""
        return pd.DataFrame(
            {
                "currentLap": range(1, 11),
                "compound": ["Soft"] * 10,
                "tire_age": range(2, 12),
                "pitstopStatus": ["On Track"] * 10,
            }
        )

    def test_no_pit_returns_all_false(self):
        df = detect_pit_events(self._base_df())
        # Skip row 0 ("Soft" != "nan" is a known session-start false positive).
        assert not df["pit_stop"].iloc[1:].any()
        assert not df["tire_change_pit"].iloc[1:].any()

    def test_compound_change_detected_as_pit(self):
        df = self._base_df()
        df.loc[5, "compound"] = "Medium"
        df.loc[5, "tire_age"] = 0
        df = detect_pit_events(df)
        assert df.loc[5, "pit_stop"]

    def test_pitstop_status_detected(self):
        df = self._base_df()
        df.loc[4, "pitstopStatus"] = "Stopped"
        df = detect_pit_events(df)
        assert df.loc[4, "pit_stop"]

    def test_tire_age_reset_detected(self):
        df = self._base_df()
        # Simular reset de edad de neumático en vuelta 6
        df.loc[5, "tire_age"] = 0
        df = detect_pit_events(df)
        assert df.loc[5, "tire_change_pit"]

    def test_no_lap_column_returns_all_false(self):
        df = pd.DataFrame({"compound": ["Soft"] * 5})
        df = detect_pit_events(df)
        assert not df["pit_stop"].any()

    def test_columns_added(self):
        df = detect_pit_events(self._base_df())
        assert "pit_stop" in df.columns
        assert "tire_change_pit" in df.columns


# ---------------------------------------------------------------------------
# build_lap_summary
# ---------------------------------------------------------------------------

class TestBuildLapSummary:
    def test_no_lap_column_returns_empty(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        result = build_lap_summary(df)
        assert result.empty

    def test_returns_one_row_per_lap(self, raw_telemetry_df):
        df = detect_pit_events(raw_telemetry_df)
        summary = build_lap_summary(df)
        assert len(summary) == raw_telemetry_df["currentLap"].nunique()

    def test_lap_time_s_column_present(self, raw_telemetry_df):
        df = detect_pit_events(raw_telemetry_df)
        summary = build_lap_summary(df)
        assert "lap_time_s" in summary.columns

    def test_compound_preserved(self, raw_telemetry_df):
        df = detect_pit_events(raw_telemetry_df)
        summary = build_lap_summary(df)
        assert (summary["compound"] == "Soft").all()

    def test_avg_wear_computed(self, raw_telemetry_df):
        df = detect_pit_events(raw_telemetry_df)
        summary = build_lap_summary(df)
        assert "avg_wear" in summary.columns
        assert summary["avg_wear"].notna().all()


# ---------------------------------------------------------------------------
# build_stints
# ---------------------------------------------------------------------------

class TestBuildStints:
    def test_no_stints_on_empty(self):
        result = build_stints(pd.DataFrame())
        assert result == []

    def test_single_stint(self, soft_laps):
        stints = build_stints(soft_laps)
        assert len(stints) == 1
        assert stints[0].compound == "Soft"

    def test_two_stints_after_pit(self, soft_laps):
        laps = soft_laps.copy()
        # Split starts at row 10: compound changes from Soft to Medium here.
        # The compound change + tire_age reset is enough to trigger a new stint.
        laps.loc[10:, "compound"] = "Medium"
        laps.loc[10:, "tire_age"] = list(range(0, len(laps) - 10))
        stints = build_stints(laps)
        assert len(stints) == 2

    def test_stint_lap_count(self, soft_laps):
        stints = build_stints(soft_laps)
        assert stints[0].total_laps == len(soft_laps)
