@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "GQOS_RISK_REFERENCE_BALANCE=9000"
title GQOS Live Engine (supervised)
:: Run under the supervisor: it auto-relaunches the engine on crash or on a
:: restart request (scripts\request_restart.py), so structural config changes
:: apply without manually reopening this window.
"%PYTHON_EXE%" "%~dp0scripts\run_supervisor.py"
echo.
echo GQOS Supervisor exited with code %ERRORLEVEL%.
pause
