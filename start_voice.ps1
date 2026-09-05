param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment not found. Run .\setup_windows.ps1 first."
}

$backendCommand = "Set-Location -LiteralPath '$root\backend'; & '$venvPython' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
$frontendCommand = "Set-Location -LiteralPath '$root\frontend'; npm run dev -- --host 127.0.0.1 --port 3000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand

Write-Host "Backend:  http://127.0.0.1:8000/health" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:3000" -ForegroundColor Green
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:3000" }
