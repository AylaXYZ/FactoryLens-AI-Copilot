$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
    throw "请先运行 start.ps1 安装环境。"
}

& ".\.venv\Scripts\python.exe" -m uvicorn factorylens.api:app --host 127.0.0.1 --port 8000

