@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install 64-bit Python 3.11, then run the checked setup:
  echo powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
  exit /b 1
)
".venv\Scripts\python.exe" -m markov_engine.service --open-browser %*
