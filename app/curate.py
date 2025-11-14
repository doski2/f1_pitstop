"""Curación de CSV → dataset por vuelta y particionado por pista/sesión/piloto."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from f1m.telemetry import DIR_CURATED
except ImportError:
    DIR_CURATED = "curated"

RAW_COLUMNS_PRIMARY_KEYS = ["timestamp", "driverNumber", "currentLap", "turnNumber"]

SESSION_ID_COLS = [
    "trackName",
    "sessionType",
    "driverFirstName",
    "driverLastName",
    "teamName",
    "driverNumber",
]

OUTPUT_BASE = Path(DIR_CURATED)


def read_csv_safe(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
        df["source_file"] = path.name
        return df
    except (
        FileNotFoundError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
    ) as e:
        print(f"[WARN] No se pudo leer {path}: {e}")
        return pd.DataFrame()


def load_track_raw(track_dir: Path) -> pd.DataFrame:
    files = list(track_dir.rglob("*.csv"))
    dfs = [read_csv_safe(f) for f in files]
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    # Normalizar timestamp a datetime
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    # Orden básico
    sort_cols = [
        c for c in ["timestamp", "currentLap", "turnNumber"] if c in df.columns
    ]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    # Eliminar duplicados exactos en claves principales disponibles
    key_cols = [c for c in RAW_COLUMNS_PRIMARY_KEYS if c in df.columns]
    if key_cols:
        df = df.drop_duplicates(subset=key_cols, keep="last")
    return df


def per_lap_last_samples(df: pd.DataFrame) -> pd.DataFrame:
    required = {"currentLap", "timestamp"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    # Tomar última muestra por vuelta (timestamp máximo) dentro de cada sesión / piloto
    group_cols = [c for c in SESSION_ID_COLS if c in df.columns] + ["currentLap"]
    last = df.sort_values("timestamp").groupby(group_cols, as_index=False).tail(1)
    # Calcular lap_time_s por diferencia de timestamp con vuelta anterior dentro de la misma sesión/piloto
    last = last.sort_values(group_cols)
    id_cols = [c for c in SESSION_ID_COLS if c in last.columns]
    last["prev_timestamp"] = last.groupby(id_cols)["timestamp"].shift(1)
    last["lap_time_s"] = (last["timestamp"] - last["prev_timestamp"]).dt.total_seconds()
    # Filtrar vueltas inválidas (lap==0 o lap_time_s <=0)
    last = last[last["currentLap"] > 0]
    # Señalar outliers básicos
    q1 = last["lap_time_s"].quantile(0.25)
    q3 = last["lap_time_s"].quantile(0.75)
    iqr = q3 - q1
    upper = q3 + 3 * iqr
    lower = max(0, q1 - 3 * iqr)
    last["lap_outlier"] = (last["lap_time_s"] < lower) | (last["lap_time_s"] > upper)
    return last


def compute_features(laps: pd.DataFrame) -> pd.DataFrame:
    if laps.empty:
        return laps
    # Pace index relativo al mejor de la sesión (por track+sessionType)
    grp = laps.groupby(["trackName", "sessionType"], dropna=False)["lap_time_s"]
    # Best lap per session (typed for static analysis)
    best_per_session: pd.Series = grp.transform("min")
    laps["pace_index"] = laps["lap_time_s"] / best_per_session
    # Degradación simple (lap time delta vs rolling median 5 vueltas) por compuesto dentro de sesión
    if "compound" in laps.columns:
        laps["rolling_med_5"] = laps.groupby(["trackName", "sessionType", "compound"])[
            "lap_time_s"
        ].transform(lambda s: s.rolling(5, min_periods=2).median())
        laps["pace_delta_rolling"] = laps["lap_time_s"] - laps["rolling_med_5"]
    # Fuel effect approximate slope per session (regresión lineal simple si hay fuel)
    if "fuel" in laps.columns and laps["fuel"].notna().sum() > 10:

        def _fuel_slope(g: pd.DataFrame):
            g2 = g.dropna(subset=["fuel", "lap_time_s"])
            if len(g2) < 6:
                return np.nan
            x = g2["fuel"].to_numpy()
            y = g2["lap_time_s"].to_numpy()
            # slope (least squares)
            xm = np.mean(x)
            ym = np.mean(y)
            denom = ((x - xm) ** 2).sum()
            if denom == 0:
                return np.nan
            slope = ((x - xm) * (y - ym)).sum() / denom
            return slope

        slopes = (
            laps.groupby(["trackName", "sessionType"])
            .apply(_fuel_slope)
            .rename("fuel_slope")
            .reset_index()
        )
        laps = laps.merge(slopes, on=["trackName", "sessionType"], how="left")
    return laps


def save_partitioned(laps: pd.DataFrame, base: Path = OUTPUT_BASE) -> None:
    if laps.empty:
        print("[INFO] Nada que guardar.")
        return
    for (track, session, driver_num, first, last), sub in laps.groupby(
        [
            c
            for c in [
                "trackName",
                "sessionType",
                "driverNumber",
                "driverFirstName",
                "driverLastName",
            ]
            if c in laps.columns
        ]
    ):
        out_dir = (
            base
            / f"track={track}"
            / f"session={session}"
            / f"driver={driver_num}_{first}_{last}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "laps.parquet"
        sub.to_parquet(out_path, index=False)


def build_summary(laps: pd.DataFrame) -> pd.DataFrame:
    if laps.empty:
        return laps
    summary = (
        laps.groupby(
            [
                "trackName",
                "sessionType",
                "driverNumber",
                "driverFirstName",
                "driverLastName",
                "compound",
            ],
            dropna=False,
        )
        .agg(
            laps=("currentLap", "nunique"),
            best_lap=("lap_time_s", "min"),
            avg_lap=("lap_time_s", "mean"),
            deg_est=("pace_delta_rolling", "mean"),
        )
        .reset_index()
    )
    return summary


def main(track_path: str):
    track_dir = Path(track_path)
    if not track_dir.exists():
        raise SystemExit(f"Ruta no existe: {track_dir}")
    print(f"[INFO] Cargando CSV desde {track_dir} ...")
    raw = load_track_raw(track_dir)
    if raw.empty:
        print("[WARN] Sin datos.")
        return
    print(f"[INFO] Registros brutos: {len(raw):,}")
    laps = per_lap_last_samples(raw)
    print(f"[INFO] Vueltas detectadas: {len(laps):,}")
    laps = compute_features(laps)
    save_partitioned(laps)
    summary = build_summary(laps)
    OUTPUT_BASE.mkdir(exist_ok=True)
    summary_path = OUTPUT_BASE / "summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"[OK] Guardado summary en {summary_path} y particiones en {OUTPUT_BASE}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Curación de datos de telemetría por pista"
    )
    parser.add_argument(
        "track_path",
        help="Ruta a carpeta de pista (por ejemplo logs_in/exported_data/Bahrain)",
    )
    args = parser.parse_args()
    main(args.track_path)
