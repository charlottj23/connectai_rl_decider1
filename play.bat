@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo CONNECT TYCOON ?? ?...
call .venv\Scripts\activate.bat

:: ?? ?? ?? (960x600, 800x500 ?)
set SCREEN_SIZE=960x600

connect-tycoon play --size %SCREEN_SIZE%
pause