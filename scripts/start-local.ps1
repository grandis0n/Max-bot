# Локальный запуск без Docker (нужны Python 3.12+ и PostgreSQL)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

if (-not (Test-Path (Join-Path $root ".env"))) {
    Write-Host "Создайте .env из .env.example" -ForegroundColor Red
    exit 1
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python не найден. Установите Python 3.12+ с python.org или: winget install Python.Python.3.12" -ForegroundColor Red
    exit 1
}

Set-Location (Join-Path $root "bot-service")
if (-not (Test-Path ".venv")) {
    & python -m venv .venv
}
& .\.venv\Scripts\pip install -r requirements.txt
Copy-Item (Join-Path $root ".env") (Join-Path $root "bot-service\.env") -Force
Set-Location (Join-Path $root "bot-service")
& .\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
