@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" "main.py"
endlocal
