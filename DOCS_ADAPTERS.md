# Guía de Adapters Multi‑Juego

Normaliza datasets de distintos juegos a un esquema común.

## Columnas Canónicas

Obligatorias: `currentLap`, `tire_age`, `compound`, `lap_time_s`.
Recomendadas: `timestamp`, `fuel`, `flTemp`..`rrTemp`, `flDeg`..`rrDeg`, `trackTemp`, `airTemp`.

## Interface

```python
def load_raw_csv(path) -> pandas.DataFrame:
    ...
```

## Pasos Nuevo Adapter

1. Copiar `adapters/stub_example.py`.
2. Leer CSV.
3. Mapear columnas.
4. Derivar `lap_time_s` si falta.
5. Tipos y orden.
6. Rellenar NaN.
7. Validar columnas clave.
8. Documentar.

## Ejemplo Mapeo

```python
COLUMN_MAP = {
  'Lap': 'currentLap',
  'TyreAge': 'tire_age',
  'Compound': 'compound',
  'LapTimeSec': 'lap_time_s'
}
```

## Futuro Selector

```python
game = st.sidebar.selectbox('Juego', ['F1 Manager 2024'])
from adapters import f1manager2024
loader = f1manager2024.load_raw_csv
```

## Buenas Prácticas

- Sin lógica de estrategia en adapter.
- Evitar dependencias pesadas.
- Tests mínimos.

Fin.
