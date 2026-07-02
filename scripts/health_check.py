import os
import sys
import html

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import MetaTrader5 as mt5

from config.settings import settings
from gqos.ops.live_guard import build_health_report, build_symbol_scoreboard, summarize_rejection_reasons


def main() -> int:
    initialized = mt5.initialize(
        login=settings.MT5_LOGIN,
        password=settings.MT5_PASSWORD,
        server=settings.MT5_SERVER,
    )
    if not initialized:
        print(f"FAIL MT5 initialize failed: {mt5.last_error()}")
        return 2

    try:
        ok, report = build_health_report()
        print(report)
        print()
        print(summarize_rejection_reasons())
        print()
        scoreboard = build_symbol_scoreboard(max_rows=30).replace("<b>", "").replace("</b>", "")
        print(html.unescape(scoreboard))
        return 0 if ok else 1
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
