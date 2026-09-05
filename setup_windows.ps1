param(
    [switch]$CpuOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"

Write-Host "VoiceVault Windows setup" -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.12+ is required but 'python' was not found on PATH."
}
if (-not (Test-Path $python)) {
    python -m venv $venv
}
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $root "backend\requirements.txt")

if (-not $CpuOnly) {
    Write-Host "Installing PyTorch CUDA wheels (falls back to the package default if unavailable)..." -ForegroundColor Yellow
    try {
        & $python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
    } catch {
        Write-Warning "CUDA wheel installation failed: $($_.Exception.Message)"
        Write-Host "Installing CPU-compatible PyTorch instead..." -ForegroundColor Yellow
        & $python -m pip install torch torchaudio
    }
} else {
    & $python -m pip install torch torchaudio
}
& $python -m pip install -r (Join-Path $root "backend\requirements-models.txt")

Push-Location (Join-Path $root "frontend")
try {
    npm install
} finally {
    Pop-Location
}

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) { Write-Host "ffmpeg: $($ffmpeg.Source)" -ForegroundColor Green }
else { Write-Warning "ffmpeg was not found. WAV works; MP3 decoding may require ffmpeg/libsndfile." }

& $python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
Write-Host "Setup completed. Run .\start_voice.ps1" -ForegroundColor Green
