@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
title GQOS Shadow Bot
"%PYTHON_EXE%" "%~dp0scripts\run_strategy_a2_shadow.py"
echo.
echo GQOS Shadow Bot exited with code %ERRORLEVEL%.
pause
