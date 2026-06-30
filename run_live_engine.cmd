@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "GQOS_RISK_REFERENCE_BALANCE=9000"
title GQOS Live Engine
"%PYTHON_EXE%" "%~dp0scripts\run_gqos_live.py"
echo.
echo GQOS Live Engine exited with code %ERRORLEVEL%.
pause
