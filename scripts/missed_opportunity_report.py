import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import MetaTrader5 as mt5

from config.settings import settings
from gqos.learning.missed_opportunity_tracker import missed_opportunity_tracker
from gqos.ops.missed_opportunity_report import build_missed_opportunity_report


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
        closed = missed_opportunity_tracker.process_pending(limit=None)
        if closed:
            print(f"Closed {closed} pending missed-opportunity simulations.")
        print(build_missed_opportunity_report())
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
