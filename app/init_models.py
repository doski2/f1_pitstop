from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, Union, Tuple, List
import pandas as pd

from strategy_model import collect_practice_data, fit_degradation_model
from strategy import load_session_csv, build_lap_summary

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

PRACTICE_LIKE = {"Practice 1","Practice 2","Practice 3","Practice","FP1","FP2","FP3"}


def discover_drivers(track_dir: Path) -> List[str]:
    drivers: List[str] = []
    if not track_dir.exists():
        return drivers
    for session in track_dir.iterdir():
        if not session.is_dir():
            continue
        for d in session.iterdir():
            if d.is_dir() and any(f.suffix == '.csv' for f in d.glob('*.csv')):
                drivers.append(d.name)
    return sorted(set(drivers))


def fallback_race_sample(track_dir: Path, track: str, driver: str, max_laps: int = 12) -> pd.DataFrame:
    """Si no hay prácticas, usa primeras vueltas de carrera para estimar modelo."""
    race_dir = track_dir / 'Race'
    if not race_dir.exists():
        return pd.DataFrame()
    frames = []
    for d in race_dir.rglob(driver):
        if d.is_dir():
            for csv in d.glob('*.csv'):
                try:
                    df = load_session_csv(csv)
                    lap_sum = build_lap_summary(df)
                    lap_sum = lap_sum[lap_sum['lap_time_s'].notna()]
                    lap_sum = lap_sum.nsmallest(max_laps, 'currentLap')
                    lap_sum['session'] = 'RaceSample'
                    frames.append(lap_sum)
                except Exception:  # noqa
                    continue
    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()


def prepare_driver_data(data_root: Path, track: str, driver: str) -> pd.DataFrame:
    base = collect_practice_data(data_root, track, driver)
    if base.empty:
        # usar fallback
        track_dir = data_root / track
        fallback = fallback_race_sample(track_dir, track, driver)
        return fallback
    return base


def save_models(models: Dict[str, Union[Tuple[float, float], Tuple[float, float, float]]], out_path: Path, meta: dict):
    serializable = {
        'metadata': meta,
        'models': {comp: list(coeffs) for comp, coeffs in models.items()}
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(serializable, indent=2))


def build_and_save(data_root: Path, track: str, driver: str, out_dir: Path) -> Path | None:
    data = prepare_driver_data(data_root, track, driver)
    if data.empty:
        print(f"[WARN] Sin datos para {driver} en {track}")
        return None
    models = fit_degradation_model(data)
    if not models:
        print(f"[WARN] Modelos no generados para {driver} (datos insuficientes)")
        return None
    meta = {
        'track': track,
        'driver': driver,
        'sessions_included': sorted(data['session'].unique()) if 'session' in data.columns else [],
        'fuel_used': any(len(v) == 3 for v in models.values())
    }
    out_path = out_dir / track / f"{driver}_model.json"
    save_models(models, out_path, meta)
    print(f"[OK] Guardado modelo: {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description='Generar modelos iniciales de degradación por pista y piloto')
    parser.add_argument('--data-root', default='logs_in/exported_data', help='Raíz de datos exportados')
    parser.add_argument('--track', required=True, help='Nombre de circuito (folder)')
    parser.add_argument('--driver', help='Piloto específico; si se omite procesa todos')
    parser.add_argument('--out-dir', default='models', help='Directorio destino')
    args = parser.parse_args()

    data_root = Path(args.data_root)
    if not data_root.exists():
        raise SystemExit(f"No existe data_root: {data_root}")
    track_dir = data_root / args.track
    if not track_dir.exists():
        raise SystemExit(f"No existe carpeta de track: {track_dir}")
    out_dir = Path(args.out_dir)

    if args.driver:
        build_and_save(data_root, args.track, args.driver, out_dir)
    else:
        drivers = discover_drivers(track_dir)
        if not drivers:
            print("[WARN] No se detectaron pilotos.")
            return
        for drv in drivers:
            build_and_save(data_root, args.track, drv, out_dir)


if __name__ == '__main__':
    main()
