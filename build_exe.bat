@echo off
setlocal
REM Build ro-bot.exe for people without Python (run on Windows with Python installed)
cd /d "%~dp0"
py -3 -m pip install -q pyinstaller -r requirements.txt
py -3 -m PyInstaller --onefile --name ro-bot --clean --noconfirm --collect-all discord bot.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
if not exist "dist\ro-bot-package" mkdir "dist\ro-bot-package"
copy /y "dist\ro-bot.exe" "dist\ro-bot-package\" >nul
copy /y "events.json" "dist\ro-bot-package\" >nul
copy /y "alert.wav" "dist\ro-bot-package\" >nul
copy /y "INSTALL.md" "dist\ro-bot-package\" >nul
echo.
echo Done: share the folder dist\ro-bot-package (ro-bot.exe + events.json + alert.wav)
echo The recipient double-clicks ro-bot.exe and enters the bot token once.
pause
