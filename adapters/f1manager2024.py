import pandas as pd
from strategy import load_session_csv

def load_raw_csv(path):
    """
    Adapter para F1 Manager 2024: carga y normaliza un archivo CSV de telemetría.
    Devuelve DataFrame con columnas estándar: lap, timestamp, compound, tire_age, lap_time_s, fuel, temps, desgaste, etc.
    """
    df = load_session_csv(path)
    # Aquí podrías renombrar columnas si hiciera falta, pero ya están alineadas
    # con el pipeline actual.
    return df
