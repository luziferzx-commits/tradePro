import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import MetaTrader5 as mt5

from config.settings import settings
from gqos.learning.continuous_market_simulator import continuous_market_simulator
from gqos.ops.continuous_market_sim_report import build_continuous_market_sim_report


def main() -> int:
    initialized = mt5.initialize(
        login=settings.MT5_LOGIN,
        password=settings.MT5_PASSWORD,
        server=settings.MT5_SERVER,
    )
    if not initialized:
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return 2
    try:
        stats = continuous_market_simulator.scan_once()
        print(f"Scan stats: {stats}")
        print(build_continuous_market_sim_report())
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
