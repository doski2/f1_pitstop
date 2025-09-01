@echo off
REM run_dashboard.bat — Lanza Streamlit desde la raíz del repo (usa .venv si existe)
REM Uso: run_dashboard.bat [PUERTO]

SET ROOT=%~dp0
cd /d "%ROOT%"

REM Preferir python del .venv si existe
IF EXIST "%ROOT%\.venv\Scripts\python.exe" (
	SET PYTHON=%ROOT%\.venv\Scripts\python.exe
) ELSE (
	SET PYTHON=python
)

REM Puerto por defecto (8501) — cambiar con argumento: run_dashboard.bat 8502
IF "%1"=="" (
	SET PORT=8501
) ELSE (
	SET PORT=%1
)

REM Ejecutar en ventana nueva (no bloquear) y abrir navegador
start "" "%PYTHON%" -m streamlit run "%ROOT%app\dashboard.py" --server.port %PORT% --logger.level=info
timeout /t 2 >nul
start "" "http://localhost:%PORT%"

exit /b 0
