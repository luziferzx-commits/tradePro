import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import MetaTrader5 as mt5

from config.settings import settings
from gqos.learning.mt5_outcome_sync import (
    enrich_existing_outcomes,
    sync_mt5_closed_deals_today,
    sync_mt5_open_positions_to_pending,
)


def main() -> int:
    ok = mt5.initialize(
        login=settings.MT5_LOGIN,
        password=settings.MT5_PASSWORD,
        server=settings.MT5_SERVER,
    )
    if not ok:
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return 2
    try:
        restored = sync_mt5_open_positions_to_pending()
        count = sync_mt5_closed_deals_today()
        enriched = enrich_existing_outcomes()
        print(f"Restored {restored} open MT5 positions into pending outcomes.")
        print(f"Backfilled {count} MT5 closed deals into live outcomes.")
        print(f"Enriched {enriched} existing outcomes with pattern metadata.")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
