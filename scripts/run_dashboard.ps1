param(
  [int]$Port = 8501
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

# Activa venv si existe
$venv = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv }

$env:PYTHONIOENCODING = "utf-8"
$script = "app\dashboard.py"

# Arranca Streamlit SIN abrir navegador
# (proceso hijo oculto; si prefieres verlo, quita -WindowStyle Hidden)
Start-Process -WindowStyle Hidden -FilePath powershell -ArgumentList @(
  "-NoProfile", "-Command",
  "streamlit run `"$script`" --server.headless true --server.port $Port"
) | Out-Null

# Espera a que el server responda (hasta ~20s)
$maxTries = 40
$ok = $false
for ($i=0; $i -lt $maxTries; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $r = Invoke-WebRequest -Uri "http://localhost:$Port/healthz" -UseBasicParsing -TimeoutSec 1
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch {
    try {
      $r2 = Invoke-WebRequest -Uri "http://localhost:$Port" -UseBasicParsing -TimeoutSec 1
      if ($r2.StatusCode -ge 200) { $ok = $true; break }
    } catch {}
  }
}

# Si no respondió dentro del timeout, informar y salir con error
if (-not $ok) {
  Write-Warning "Streamlit no respondió en http://localhost:$Port dentro del timeout."
  Pop-Location
  exit 1
}

# Abre exactamente una pestaña (solo si OK)
Start-Process "http://localhost:$Port"

Pop-Location
