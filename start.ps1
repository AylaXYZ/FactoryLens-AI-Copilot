$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
    & ".\.venv\Scripts\python.exe" -m pip install -e ".[models,dev]"
} elseif (-not (& ".\.venv\Scripts\python.exe" -m pip show factorylens-rag-copilot 2>$null)) {
    & ".\.venv\Scripts\python.exe" -m pip install -e ".[models,dev]"
}

& ".\.venv\Scripts\python.exe" "scripts\bootstrap.py"
& ".\.venv\Scripts\python.exe" -m streamlit run app.py
