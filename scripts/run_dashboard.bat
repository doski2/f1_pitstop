@echo off
setlocal
set PORT=8501

REM Activa venv si existe
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

REM Arranca streamlit sin abrir navegador (en segundo plano)
start "" /b cmd /c "streamlit run app\dashboard.py --server.headless true --server.port %PORT%"

REM Espera ~20s a que responda
for /l %%i in (1,1,40) do (
  >nul 2>nul powershell -NoProfile -Command "try{(Invoke-WebRequest -Uri http://localhost:%PORT%/ -UseBasicParsing -TimeoutSec 1)|Out-Null; exit 0}catch{exit 1}"
  if not errorlevel 1 goto :open
  ping -n 2 127.0.0.1 >nul
)
:open
start "" "http://localhost:%PORT%"
endlocal
