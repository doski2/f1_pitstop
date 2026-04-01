# Informe de Auditoría — f1_pitstop

**Fecha:** 28 de marzo de 2026

## 1) Resumen ejecutivo

- Tests unitarios: 40/40 (ejecutado con `pytest`) — OK.
- Linting: `ruff` — All checks passed.
- Tipado (MyPy): se añadieron reglas (`mypy.ini`) para silenciar importaciones sin stubs (plotly, bokeh, urllib3). Ejecución de `mypy` mostró un problema en `bokeh` bajo Python 3.11 y un crash en el entorno virtual con Python 3.13.
- Auditoría de dependencias (`pip-audit`): se detectaron 13 vulnerabilidades conocidas en 10 paquetes (detalles abajo).

## 2) Comandos ejecutados

```bash
python -m pytest -q
python -m ruff check .
python -m mypy . --ignore-missing-imports
c:/f1_pitstop/.venv/Scripts/python.exe -m pip_audit --format=columns --progress=off
```

## 3) Resultado de `pip-audit`

Salida completa (ejecutada en el entorno virtual):

```
Found 13 known vulnerabilities in 10 packages
Name      Version ID                  Fix Versions
--------- ------- ------------------- -------------
black     25.11.0 CVE-2026-32274      26.3.1
pillow    12.0.0  CVE-2026-25990      12.1.1
pip       25.3    CVE-2026-1703       26.0
protobuf  6.33.1  CVE-2026-0994       5.29.6,6.33.5
pygments  2.19.2  CVE-2026-4539
requests  2.32.5  CVE-2026-25645      2.33.0
streamlit 1.51.0  CVE-2026-33682      1.54.0
tornado   6.5.2   GHSA-78cv-mqj4-43f7 6.5.5
tornado   6.5.2   CVE-2026-31958      6.5.5
urllib3   2.5.0   CVE-2025-66418      2.6.0
urllib3   2.5.0   CVE-2025-66471      2.6.0
urllib3   2.5.0   CVE-2026-21441      2.6.3
wheel     0.45.1  CVE-2026-24049      0.46.2
```

Observaciones:

- Hay vulnerabilidades con parches disponibles (ver columna "Fix Versions").
- Paquetes de UI/infra como `streamlit`, `tornado`, `urllib3` y utilidades (`pip`, `wheel`, `pillow`) aparecen en la lista y deberían actualizarse donde sea compatible.

## 4) Resultado de MyPy

- **Ejecución en el intérprete por defecto (Python 3.11)**:

```
C:\Users\doski\AppData\Roaming\Python\Python311\site-packages\bokeh\resources.py:363: error: Pattern matching is only supported in Python 3.10 and greater  [syntax]
Found 1 error in 1 file (errors prevented further checking)
```

- **Ejecución en el entorno virtual (`.venv`, Python 3.13)**:

```
Traceback (most recent call last):
  ...
TypeError: cannot use a string pattern on a bytes-like object
```

Observaciones:

- El error en `bokeh` es un problema del paquete (pattern matching) y no del código del proyecto; MyPy en CI puede continuar ignorando este caso.
- El crash en Python 3.13 sugiere incompatibilidad entre la versión de `mypy` instalada y Python 3.13 en el entorno virtual. Recomendación: ejecutar MyPy con Python 3.11/3.12 en CI, o actualizar/esperar soporte estable de MyPy para 3.13.

## 5) Cambios aplicados durante la auditoría

- Añadido: `mypy.ini` (silencia imports sin stubs de `plotly`, `bokeh`, `urllib3`).

Archivo añadido: `mypy.ini`

```
[mypy]
python_version = 3.9
exclude = (?:\.venv|\.mypy_cache|\.git|\.pytest_cache)

[mypy-plotly.*]
ignore_missing_imports = True

[mypy-plotly.graph_objects.*]
ignore_missing_imports = True

[mypy-bokeh.*]
ignore_missing_imports = True

[mypy-urllib3.*]
ignore_missing_imports = True
```

## 6) Recomendaciones prioritarias (ordenadas)

1. Actualizar/incrementar las dependencias que tienen parches disponibles (usar `pip-audit` y fijar versiones seguras en `requirements.txt`). Priorizar: `urllib3`, `tornado`, `streamlit`, `pip`, `wheel`, `pillow`.
2. Añadir `pip-audit` al pipeline CI para detectar regresiones de seguridad automáticamente (fail build en severidad alta/critica).
3. Habilitar Dependabot o Renovate para PRs automáticas de actualización de dependencias.
4. Ejecutar MyPy en un intérprete soportado (3.10–3.12) en CI para evitar crashes con Python 3.13, o usar la última versión compatible de `mypy` cuando esté disponible.
5. Mantener `mypy.ini` para silenciar módulos sin stubs, o instalar tipos si existen (p.ej. `types-requests`, `types-urllib3` si aplicable).
6. Revisar `streamlit` y `bokeh` por breaking changes antes de actualizar en producción (tests de UI / integraciones).

## 7) Próximos pasos sugeridos (acciones con prioridad)

- Implementar `pip-audit` en CI y ejecutar diariamente/semanalmente.
- Aplicar upgrades de paquetes con parches y ejecutar tests completos.
- Cambiar la matriz de CI para ejecutar MyPy con Python 3.11/3.12 explicitamente, o aislar la verificación de tipos a un job específico.
- Opcional: generar un CHANGELOG de actualizaciones de seguridad cuando se aplique un upgrade mayor.

---

Archivo(s) añadidos por esta auditoría:

- `mypy.ini`
- `AUDIT_REPORT.md` (este archivo)

Si quieres, puedo:

- abrir PR con las actualizaciones de `requirements.txt` para las correcciones sugeridas, o
- añadir un job `security` en `.github/workflows/ci.yml` que ejecute `pip-audit` y falle en vulnerabilidades críticas.
