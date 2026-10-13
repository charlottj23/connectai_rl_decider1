@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo CONNECT TYCOON 실행 중...
call .venv\Scripts\activate.bat

:: 화면 크기 설정 (기본: 1280x800, 축소: 960x600, 800x500 등)
set SCREEN_SIZE=960x600

connect-tycoon play --size %SCREEN_SIZE%
pause
