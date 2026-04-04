from __future__ import annotations

from .constants import COMPOUND_CANONICAL_MAP, COMPOUND_COLOR_MAP, COMPOUND_DISPLAY_MAP
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


def display_compound(raw: str) -> str:
    """Return enriched display label for a compound name.

    Known Pirelli spec IDs (C1-C5) get a hardness suffix.
    Plain category names (Hard/Medium/Soft/...) are returned unchanged.
    Any unrecognised value is returned as-is.
    """
    return COMPOUND_DISPLAY_MAP.get(str(raw), str(raw))


def compound_color(raw: str) -> str:
    """Return the F1-standard hex color for a compound or its display label."""
    return COMPOUND_COLOR_MAP.get(display_compound(raw), COMPOUND_COLOR_MAP.get(str(raw), "#888888"))


def canonical_compound(raw: str) -> str:
    """Normalise any raw compound string to its canonical hardness category.

    Examples
    --------
    canonical_compound("C3")  → "Soft"
    canonical_compound("C4")  → "Soft"
    canonical_compound("C10") → "Hard"
    canonical_compound("Soft") → "Soft"

    Unknown values are returned unchanged so the model can still attempt a fit.
    """
    return COMPOUND_CANONICAL_MAP.get(str(raw), str(raw))


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
                    # Directory format is "driver=14_Fernando_Alonso" (underscores).
                    # Normalise both sides to underscores before matching so
                    # "Fernando Alonso" matches "driver=14_Fernando_Alonso".
                    if driver.replace(" ", "_") in driver_dir.name:
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
