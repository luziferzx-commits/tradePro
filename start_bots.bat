@echo off
cd /d "%~dp0"
echo ===================================================
echo     Starting TradePro GQOS System
echo ===================================================
echo.
echo Launching Live Engine and Shadow Bot in separate windows...
echo.

:: Kill any existing instances of the bots to prevent duplicates
echo Stopping existing bots...
wmic process where "name='python.exe' and commandline like '%%run_gqos_live.py%%'" call terminate >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%run_strategy_a2_shadow.py%%'" call terminate >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%streamlit%%'" call terminate >nul 2>&1
ping -n 2 127.0.0.1 >nul
echo.

:: Launch Windows Terminal with multiple tabs
wt -d . cmd /k "title GQOS Live Engine && python scripts\run_gqos_live.py" ; new-tab -d . cmd /k "title GQOS Shadow Bot && python scripts\run_strategy_a2_shadow.py" ; new-tab -d . cmd /k "title GQOS Dashboard && start chrome http://localhost:8501 && streamlit run dashboard.py --server.headless=true"

pause
