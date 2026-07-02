@echo off
cd /d "%~dp0"
title GQOS Dashboard
start chrome http://localhost:8501
streamlit run dashboard.py --server.headless=true
echo.
echo GQOS Dashboard exited with code %ERRORLEVEL%.
pause
