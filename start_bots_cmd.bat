@echo off
echo Starting bots in standard CMD windows...
start "GQOS Live Engine" cmd /k "python scripts\run_gqos_live.py"
start "GQOS Shadow Bot" cmd /k "python scripts\run_strategy_a2_shadow.py"
start "GQOS Dashboard" cmd /k "start chrome http://localhost:8501 && streamlit run dashboard.py --server.headless=true"
exit
