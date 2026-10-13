@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat

:: Window size (default: 1280x800 -> reduced: 960x600, 800x500, etc.)
set SCREEN_SIZE=960x600

connect-tycoon play --size %SCREEN_SIZE%
pause

