@echo off
cd /d "%~dp0"
python filenamer.py
if errorlevel 1 (
    echo.
    echo If Python is not installed, download it from https://www.python.org/downloads/
    pause
)