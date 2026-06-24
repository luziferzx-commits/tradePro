# ADR-0041: Execution Quality & Resilience Boundary

## Context

After establishing multi-broker execution (M22), it became clear that executing orders is only half the battle. Poor execution quality (slippage, rate limiting, and network dropouts) can silently destroy alpha. We needed a robust framework to handle exchange API limits gracefully and meticulously track slippage between the Alpha's generated "Arrival Price" and the actual filled price.

## Decision 1: Thread-Safe Token Bucket for Rate Limiting

We implemented a `TokenBucket` algorithm in `gqos/live/resilience.py`.

* **Rationale**: Exchanges like Binance strictly ban IPs that spam the API. Rather than risking a global 429 ban, our local Token Bucket simulates the exchange's limits. If our OMS tries to burst 50 orders instantly, the bucket intercepts and locally rejects/delays them, ensuring we never exceed the exchange threshold. It uses a `threading.Lock()` to ensure thread safety across concurrent order emissions.

## Decision 2: Smart Retry Policy with Idempotency

We implemented a `@retry_policy` decorator for network calls.

* **Rationale**: Blind retries are dangerous. If we receive a 400 (Invalid Order), retrying is useless. If we receive a 401 (Unauthorized), it implies compromised keys and we must trigger the Global Kill Switch. We only apply Exponential Backoff to 500 (Internal Server Error) and standard delay to 429 (Rate Limit). Crucially, to ensure idempotency, the retry logic enforces the exact same `client_order_id`, ensuring the exchange will inherently deduplicate a retry if the first attempt was silently successful.

## Decision 3: Metadata Cache over Hardcoding

Instead of hardcoding precision boundaries, `BinanceAdapter` uses `MetadataCache`.

* **Rationale**: Exchange `LOT_SIZE` and `PRICE_FILTER` rules change over time. By dynamically parsing `/api/v3/exchangeInfo` at boot (and refreshing periodically), our precision adjustment logic is always in sync with real market rules, preventing rejected orders due to stale decimals.

## Decision 4: Execution Quality VWAP Slippage

We calculate Slippage BPS dynamically upon the completion of a final fill.

* **Rationale**: Slippage is calculated as the difference between the `Arrival Price` (the market price at the precise moment the forecast fired) and the `Fill VWAP` (the volume-weighted average price of all partial fills). By tracking this, Quant Researchers can quantify exact execution bleed. We export this to Prometheus for live dashboards and to an append-only JSONL file for end-of-month Alpha calibration.

## Status

Approved and implemented in M22.5.
