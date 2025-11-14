# Contribuir

## Flujo

1. Crea una rama: `git checkout -b feature/<nombre>`
2. Activa pre-commit:

   ```bash
   pip install pre-commit
   pre-commit install
   ```

3. Ejecuta `make qa` antes de subir cambios.
4. Envía un PR con:

- Descripción del cambio
- Notas de compatibilidad (si aplica)
- Ejemplo mínimo (sin datos privados)

## Estilo

- Python 3.10+
- Black (line-length=100) y Ruff
- Tipado opcional (mypy permisivo)
- CI/CD con GitHub Actions (linting automático)

## Pruebas

- Aún no hay dataset de prueba público. Evita subir CSV reales.
- Si añades tests, colócalos en `tests/` y usa `pytest`.
- Ejecuta `python benchmark_performance.py` y `python benchmark_dashboard.py` para validar rendimiento

## Rendimiento

Antes de contribuir cambios que puedan afectar el rendimiento:

1. Ejecuta las pruebas de rendimiento: `python benchmark_performance.py`
2. Verifica que no hay regresiones significativas
3. Si introduces optimizaciones, documenta las mejoras en `PERFORMANCE_README.md`

## Roadmap sugerido

- Métricas (MAE/R²) visibles en UI
- Soporte Safety Car / lluvia (flags en datasets)
- Más optimizaciones de rendimiento
- Tests de integración automatizados
