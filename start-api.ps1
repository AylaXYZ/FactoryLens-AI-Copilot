$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
    throw "Virtual environment not found. Run start.ps1 first."
}

& ".\.venv\Scripts\python.exe" -m uvicorn factorylens.api:app --host 127.0.0.1 --port 8000
