@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
title GQOS Health Check
"%PYTHON_EXE%" "%~dp0scripts\health_check.py"
echo.
echo Health check exited with code %ERRORLEVEL%.
pause
