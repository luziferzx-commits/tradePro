import pandas as pd

from gqos.learning.edge_metrics import grouped_edge, rolling_edge


def test_rolling_edge_calculates_recent_windows():
    df = pd.DataFrame(
        {
            "close_time": pd.date_range("2026-01-01", periods=4, freq="h"),
            "realized_pnl": [10.0, -5.0, 20.0, -10.0],
            "actual_r": [1.0, -0.5, 2.0, -1.0],
            "symbol": ["A", "A", "B", "B"],
        }
    )

    roll = rolling_edge(df, windows=(2, 4))

    assert list(roll["window"]) == [2, 4]
    assert roll.loc[roll["window"] == 4, "trades"].iloc[0] == 4
    assert roll.loc[roll["window"] == 4, "profit_factor"].iloc[0] == 2.0


def test_grouped_edge_summarizes_by_symbol():
    df = pd.DataFrame(
        {
            "realized_pnl": [10.0, -5.0, 20.0, 5.0],
            "symbol": ["A", "A", "B", "B"],
        }
    )

    grouped = grouped_edge(df, group_col="symbol", min_trades=2)

    assert set(grouped["symbol"]) == {"A", "B"}
    assert grouped.iloc[0]["symbol"] == "B"
