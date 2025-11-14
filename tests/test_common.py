"""Tests for f1m.common module."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from f1m.common import collect_practice_data


class TestCollectPracticeData:
    """Test data collection functions."""

    def test_collect_practice_data_empty(self, tmp_path):
        """Test collecting practice data with no files."""
        # Use data_root such that data_root.parent.parent == tmp_path
        data_root = tmp_path / "logs_in" / "Bahrain"
        data_root.mkdir(parents=True)

        result = collect_practice_data(data_root, "Bahrain", "Fernando")

        assert result.empty
        # The function returns an empty DataFrame with no columns when no data is found
        assert result.empty

    def test_collect_practice_data_with_files(self, tmp_path):
        """Test collecting practice data with sample files."""
        # Create directory structure
        practice_dir = tmp_path / "curated" / "track=Bahrain" / "session=Practice 1"
        practice_dir.mkdir(parents=True)

        # Create sample data for Fernando Alonso
        driver_dir = practice_dir / "driver=14_Fernando_Alonso"
        driver_dir.mkdir()

        # Create sample parquet file with correct columns
        sample_data = pd.DataFrame(
            {
                "lap_time_s": [90.5, 89.8],
                "compound": ["SOFT", "SOFT"],
                "tire_age": [1, 2],
                "currentLap": [1, 2],
                "driverNumber": [14, 14],
                "sessionType": ["Practice 1", "Practice 1"],
            }
        )
        sample_data.to_parquet(driver_dir / "laps.parquet")

        # Use data_root such that data_root.parent.parent == tmp_path
        data_root = tmp_path / "logs_in" / "Bahrain"
        data_root.mkdir(parents=True)

        result = collect_practice_data(data_root, "Bahrain", "Fernando")

        assert not result.empty
        assert len(result) == 2
        assert result["driverNumber"].iloc[0] == 14
        # Check lap_time_s values with tolerance for floating point precision
        np.testing.assert_array_almost_equal(
            sorted(result["lap_time_s"].tolist()), sorted([90.5, 89.8]), decimal=5
        )

    def test_collect_practice_data_missing_directory(self, tmp_path):
        """Test collecting practice data from non-existent directory."""
        result = collect_practice_data(tmp_path / "nonexistent", "Bahrain", "Fernando")

        assert result.empty
        assert result.empty
