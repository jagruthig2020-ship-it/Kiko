@echo off
setlocal
cd /d "%~dp0"
title KIKO Interactive - Windows Screen Coach
if exist ".venv\Scripts\python.exe" goto INSTALL
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 -m venv .venv >nul 2>nul
  if exist ".venv\Scripts\python.exe" goto INSTALL
  py -3.12 -m venv .venv >nul 2>nul
  if exist ".venv\Scripts\python.exe" goto INSTALL
  py -3 -m venv .venv >nul 2>nul
  if exist ".venv\Scripts\python.exe" goto INSTALL
)
where python >nul 2>nul
if not errorlevel 1 python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo Python 3 not found. Install Python 3.11 or later.
  pause
  exit /b 1
)
:INSTALL
".venv\Scripts\python.exe" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
  echo Package installation failed; send the error above.
  pause
  exit /b 1
)
echo Starting KIKO Interactive. Browser should open automatically.
".venv\Scripts\python.exe" server.py
if errorlevel 1 echo KIKO stopped with an error.
pause
