@echo off
chcp 65001 >nul
title RO: The New World - Event Reminder Bot
cd /d "%~dp0"

where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo ไม่พบ Python ในเครื่อง
  echo กรุณาติดตั้งจาก https://www.python.org/downloads/  ^(ติ๊ก "Add python.exe to PATH" ตอนติดตั้ง^)
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo กำลังเตรียมสภาพแวดล้อมครั้งแรก...
  %PY% -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

echo.
echo เริ่มบอท... ปิดหน้าต่างนี้ = บอทหยุดทำงาน
echo.
".venv\Scripts\python.exe" bot.py
pause
