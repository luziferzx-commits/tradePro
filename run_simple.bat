@echo off
cd /d "%~dp0"
echo Killing background bots...
taskkill /F /IM python.exe /T >nul 2>&1
echo Launching Live Engine, Shadow Bot, and Dashboard...
start cmd /k "title GQOS Live Engine && python scripts\run_gqos_live.py"
start cmd /k "title GQOS Shadow Bot && python scripts\run_strategy_a2_shadow.py"
start cmd /k "title GQOS Dashboard && streamlit run dashboard.py"
exit
