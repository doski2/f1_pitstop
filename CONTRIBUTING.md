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
- Python 3.9+
- Black (line-length=100) y Ruff
- Tipado opcional (mypy permisivo)

## Pruebas
- Aún no hay dataset de prueba público. Evita subir CSV reales.
- Si añades tests, colócalos en `tests/` y usa `pytest`.

## Roadmap sugerido
- Métricas (MAE/R²) visibles en UI
- Soporte Safety Car / lluvia (flags en datasets)
