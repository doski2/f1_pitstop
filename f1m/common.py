from __future__ import annotations

from .imports import Path, pd
from .telemetry import (
    COL_LAP_TIME,
    DIR_CURATED,
    build_lap_summary,
    load_session_csv,
    optimize_dataframe_memory,
)

PRACTICE_SESSION_NAMES = {
    "Practice 1",
    "Practice 2",
    "Practice 3",
    "Practice",
    "FP1",
    "FP2",
    "FP3",
}


def collect_practice_data(data_root: Path, track: str, driver: str) -> pd.DataFrame:
    """Aggregate lap summaries from all practice sessions for given track & driver.

    Optimized to read from curated Parquet files instead of processing CSVs.
    """
    # Try to use curated data first
    project_root = data_root.parent.parent
    curated_root = project_root / DIR_CURATED

    frames = []

    # Check if curated data exists
    if curated_root.exists():
        track_dir = curated_root / f"track={track}"
        if track_dir.exists():
            for session_dir in track_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                session_name = session_dir.name.replace("session=", "")
                if (
                    session_name not in PRACTICE_SESSION_NAMES
                    and not session_name.startswith("Practice")
                ):
                    continue
                # Find driver directory matching the driver name
                for driver_dir in session_dir.iterdir():
                    if not driver_dir.is_dir():
                        continue
                    if driver in driver_dir.name:  # Match by driver name/number
                        parquet_file = driver_dir / "laps.parquet"
                        if parquet_file.exists():
                            try:
                                lap_sum = pd.read_parquet(parquet_file)
                                # Rename sessionType to session for consistency
                                if "sessionType" in lap_sum.columns:
                                    lap_sum = lap_sum.rename(
                                        columns={"sessionType": "session"}
                                    )
                                frames.append(lap_sum)
                            except (
                                FileNotFoundError,
                                PermissionError,
                                pd.errors.EmptyDataError,
                                ValueError,
                                KeyError,
                            ):
                                # Skip corrupted or inaccessible Parquet files
                                continue

    # Fallback to processing CSVs if no curated data found
    if not frames:
        track_dir = data_root / track
        if not track_dir.exists():
            return pd.DataFrame()
        for session_dir in track_dir.iterdir():
            if not session_dir.is_dir():
                continue
            if (
                session_dir.name not in PRACTICE_SESSION_NAMES
                and not session_dir.name.startswith("Practice")
            ):
                continue
            # Search within driver subdirs
            for d in session_dir.rglob(driver):
                if d.is_dir():
                    for csv in d.glob("*.csv"):
                        try:
                            df = load_session_csv(csv)
                            lap_sum = build_lap_summary(df)
                            lap_sum["session"] = session_dir.name
                            frames.append(lap_sum)
                        except (
                            FileNotFoundError,
                            PermissionError,
                            pd.errors.EmptyDataError,
                            pd.errors.ParserError,
                            KeyError,
                            ValueError,
                        ):
                            # Skip corrupted or inaccessible CSV files
                            continue

    if frames:
        out = pd.concat(frames, ignore_index=True)
        # Clean lap_time_s (drop None / zeros)
        out = out[(out[COL_LAP_TIME].notna()) & (out[COL_LAP_TIME] > 0)]
        # Optimize memory usage
        out = optimize_dataframe_memory(out)
        return out
    return pd.DataFrame()
