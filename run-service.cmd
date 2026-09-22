@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create and activate a Python environment using the Local service setup in README.md.
  exit /b 1
)
".venv\Scripts\python.exe" -m markov_engine.service --open-browser %*
