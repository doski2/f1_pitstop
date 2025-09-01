<#
PowerShell helper para arrancar el dashboard y abrir el navegador.
Uso: .\run_dashboard.ps1  # desde la raíz del repo
Opciones: --Port <n> para cambiar puerto
#>
param(
    [int]$Port = 8501
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $root "app\dashboard.py"
$venv_python = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venv_python) {
    $python = $venv_python
} else {
    $python = "python"
}

Write-Host "Starting Streamlit using: $python" -ForegroundColor Cyan
Start-Process -FilePath $python -ArgumentList "-m", "streamlit", "run", "$script", "--server.port", "$Port", "--logger.level=info" -WindowStyle Minimized
Start-Sleep -Seconds 2
Write-Host "Opening http://localhost:$Port" -ForegroundColor Green
Start-Process "http://localhost:$Port"
