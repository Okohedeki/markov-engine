@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create the project environment and install dependencies first:
  echo py -3.11 -m venv .venv
  echo .venv\Scripts\python.exe -m pip install -e .
  exit /b 1
)
".venv\Scripts\python.exe" -m markov_engine.service %*
