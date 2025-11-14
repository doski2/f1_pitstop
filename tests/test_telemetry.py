"""Tests for f1m.telemetry module."""

import numpy as np
import pandas as pd
import pytest

from f1m.telemetry import (
    COL_COMPOUND,
    COL_LAP,
    COL_LAP_TIME,
    COL_TIRE_AGE,
    _parse_lap_time_to_seconds,
    build_lap_summary,
    load_session_csv,
    optimize_dataframe_memory,
)


class TestOptimizeDataFrameMemory:
    """Test memory optimization functions."""

    def test_optimize_empty_dataframe(self):
        """Test optimization of empty DataFrame."""
        df = pd.DataFrame()
        result = optimize_dataframe_memory(df)
        assert result.empty

    def test_optimize_numeric_columns(self):
        """Test downcasting of numeric columns."""
        df = pd.DataFrame(
            {
                "int_col": [1, 2, 3, 4, 5],
                "float_col": [1.1, 2.2, 3.3, 4.4, 5.5],
                "str_col": ["a", "b", "c", "d", "e"],
            }
        )

        # Convert to larger types first
        df["int_col"] = df["int_col"].astype(np.int64)
        df["float_col"] = df["float_col"].astype(np.float64)

        result = optimize_dataframe_memory(df)

        # Check that int64 was downcasted
        assert result["int_col"].dtype == np.int8
        # Check that float64 was downcasted
        assert result["float_col"].dtype == np.float32
        # Check that string column remained unchanged
        assert result["str_col"].dtype == object


class TestLoadSessionCSV:
    """Test CSV loading functions."""

    def test_load_session_csv_basic(self, tmp_path):
        """Test basic CSV loading."""
        csv_content = """timestamp,currentLap,lap_time_s,compound,tire_age
2023-01-01 10:00:00,1,95.5,SOFT,0
2023-01-01 10:01:35,2,94.2,SOFT,1
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        result = load_session_csv(csv_file)

        assert len(result) == 2
        assert COL_LAP in result.columns
        assert pd.api.types.is_datetime64_any_dtype(result["timestamp"])
        assert result[COL_LAP].tolist() == [1, 2]

    def test_load_session_csv_with_timestamp_sorting(self, tmp_path):
        """Test CSV loading with timestamp sorting."""
        # Create CSV with unsorted timestamps
        csv_content = """timestamp,currentLap,lap_time_s,compound,tire_age
2023-01-01 10:01:35,2,94.2,SOFT,1
2023-01-01 10:00:00,1,95.5,SOFT,0
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        result = load_session_csv(csv_file)

        # Should be sorted by timestamp
        assert result[COL_LAP].tolist() == [1, 2]


class TestBuildLapSummary:
    """Test lap summary building functions."""

    def test_build_lap_summary_basic(self):
        """Test basic lap summary building."""
        # Create mock telemetry data
        telemetry_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2023-01-01 10:00:00", periods=10, freq="35s"
                ),
                COL_LAP: [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
                "lastLapTime": [
                    95.5,
                    95.5,
                    95.5,
                    95.5,
                    95.5,
                    94.2,
                    94.2,
                    94.2,
                    94.2,
                    94.2,
                ],
                COL_COMPOUND: ["SOFT"] * 10,
                COL_TIRE_AGE: list(range(10)),
                "tire_age": list(range(10)),  # Duplicate for mapping
            }
        )

        result = build_lap_summary(telemetry_data)

        assert len(result) == 2  # Two laps
        assert COL_LAP_TIME in result.columns
        assert COL_COMPOUND in result.columns
        assert COL_TIRE_AGE in result.columns

        # Check first lap
        first_lap = result[result[COL_LAP] == 1].iloc[0]
        assert first_lap[COL_LAP_TIME] == 95.5
        assert first_lap[COL_COMPOUND] == "SOFT"
        assert first_lap[COL_TIRE_AGE] == 4  # Max tire age for lap 1

    def test_build_lap_summary_empty(self):
        """Test lap summary building with empty data."""
        telemetry_data = pd.DataFrame()
        result = build_lap_summary(telemetry_data)
        assert result.empty


class TestConstants:
    """Test that constants are properly defined."""

    def test_column_constants(self):
        """Test that column name constants are strings."""
        assert isinstance(COL_LAP, str)
        assert isinstance(COL_LAP_TIME, str)
        assert isinstance(COL_COMPOUND, str)
        assert isinstance(COL_TIRE_AGE, str)

    def test_column_constant_values(self):
        """Test that column constants have expected values."""
        assert COL_LAP == "currentLap"
        assert COL_LAP_TIME == "lap_time_s"
        assert COL_COMPOUND == "compound"
        assert COL_TIRE_AGE == "tire_age"


class TestParseLapTimeToSeconds:
    """Test lap time parsing function."""

    def test_parse_seconds_float(self):
        """Test parsing float seconds."""
        assert _parse_lap_time_to_seconds(95.5) == 95.5
        assert _parse_lap_time_to_seconds(0.0) == 0.0

    def test_parse_seconds_int(self):
        """Test parsing integer seconds."""
        assert _parse_lap_time_to_seconds(90) == 90.0
        assert _parse_lap_time_to_seconds(0) == 0.0

    def test_parse_mm_ss_format(self):
        """Test parsing MM:SS.xxx format."""
        assert _parse_lap_time_to_seconds("1:30.500") == 90.5
        assert _parse_lap_time_to_seconds("0:45.000") == 45.0
        assert _parse_lap_time_to_seconds("2:15.250") == 135.25

    def test_parse_ss_format(self):
        """Test parsing SS.xxx format (no minutes)."""
        assert _parse_lap_time_to_seconds("45.500") == 45.5
        assert _parse_lap_time_to_seconds("90.000") == 90.0

    def test_parse_none_values(self):
        """Test parsing None and NaN values."""
        assert _parse_lap_time_to_seconds(None) is None
        assert _parse_lap_time_to_seconds(float("nan")) is None

    def test_parse_invalid_strings(self):
        """Test parsing invalid string formats."""
        assert _parse_lap_time_to_seconds("invalid") is None
        assert _parse_lap_time_to_seconds("12:34:56") is None
        assert _parse_lap_time_to_seconds("") is None
        assert _parse_lap_time_to_seconds("abc") is None

    def test_parse_whitespace_strings(self):
        """Test parsing strings with whitespace."""
        assert _parse_lap_time_to_seconds(" 45.500 ") == 45.5
        assert _parse_lap_time_to_seconds(" 1:30.500 ") == 90.5

    def test_memoization(self):
        """Test that function is memoized (same result for same input)."""
        # Call multiple times with same input
        result1 = _parse_lap_time_to_seconds("1:30.500")
        result2 = _parse_lap_time_to_seconds("1:30.500")
        result3 = _parse_lap_time_to_seconds("1:30.500")

        assert result1 == result2 == result3 == 90.5
