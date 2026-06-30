@echo off
cd /d "%~dp0"
echo ===================================================
echo     Starting TradePro GQOS System
echo ===================================================
echo.
echo Launching Live Engine, Shadow Bot, and Dashboard in one Windows Terminal...
echo.

:: Kill any existing instances of the bots to prevent duplicates
echo Stopping existing bots...
wmic process where "name='python.exe' and commandline like '%%run_gqos_live.py%%'" call terminate >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%run_strategy_a2_shadow.py%%'" call terminate >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%streamlit%%'" call terminate >nul 2>&1
ping -n 2 127.0.0.1 >nul
echo.

:: Launch one Windows Terminal window with separate tabs. Helper scripts keep
:: startup errors visible instead of the tab closing immediately.
wt ^
  new-tab --title "GQOS Live Engine" -d "%CD%" cmd /k "%CD%\run_live_engine.cmd" ^
  ; new-tab --title "GQOS Shadow Bot" -d "%CD%" cmd /k "%CD%\run_shadow_bot.cmd" ^
  ; new-tab --title "GQOS Dashboard" -d "%CD%" cmd /k "%CD%\run_dashboard.cmd"

pause
