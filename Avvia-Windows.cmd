@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python avvia.py %*
) else (
  py -3 avvia.py %*
)
if errorlevel 1 pause
