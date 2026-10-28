@echo off
chcp 65001 >nul
REM สร้างไฟล์ ro-bot.exe สำหรับแจกให้คนที่ไม่มี Python (รันสคริปต์นี้บน Windows ที่มี Python)
cd /d "%~dp0"
py -3 -m pip install -q pyinstaller -r requirements.txt
py -3 -m PyInstaller --onefile --name ro-bot --clean --noconfirm bot.py
if errorlevel 1 ( echo build ล้มเหลว & pause & exit /b 1 )
mkdir dist\ro-bot-package 2>nul
copy /y dist\ro-bot.exe dist\ro-bot-package\ >nul
copy /y events.json dist\ro-bot-package\ >nul
copy /y alert.wav dist\ro-bot-package\ >nul
copy /y README.md dist\ro-bot-package\ >nul
echo.
echo เสร็จแล้ว: แจกโฟลเดอร์ dist\ro-bot-package ^(มี ro-bot.exe + events.json^)
echo ผู้รับแค่ดับเบิลคลิก ro-bot.exe แล้วใส่โทเคนครั้งแรก
pause
