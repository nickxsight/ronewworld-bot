@echo off
setlocal
title RO: The New World - Event Reminder Bot
cd /d "%~dp0"

set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo.
  echo [ERROR] Python not found.
  echo Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during setup.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup, please wait...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Could not create virtual environment.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Could not install requirements. Check your internet connection.
  pause
  exit /b 1
)

echo.
echo Starting bot... keep this window open. Closing it stops the bot.
echo.
".venv\Scripts\python.exe" -X utf8 bot.py
echo.
pause
