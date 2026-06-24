# ADR-0015: Volatility-Based Position Sizing

## Context

In Milestone 9B (M9B), GQOS advances the Position Sizing Layer to incorporate dynamic Volatility-Based rules. Previous iterations primarily used Fixed Fractional, Fixed Risk, or Kelly Criterion rules where risk was implicitly defined by static stop losses and account equity. As an institutional quant decision platform, GQOS must adjust sizing in response to current market volatility regimes.

## Decision 1: `VolatilityMetrics` Embedded in Request

To maintain the core statelessness of `PositionSizingEngine`, we introduced a new `VolatilityMetrics` dataclass embedded inside `SizingRequest` and `SizePositionCommand`.

```python
@dataclass(frozen=True)
class VolatilityMetrics:
    atr: Decimal
    annualized_volatility: Optional[Decimal] = None
```

**Rationale:**
* **Stateless Validation:** Volatility inputs are captured at the point of command dispatch. This ensures the sizing layer is pure.
* **Deterministic Replay:** The exact ATR and annualized volatility used to size a trade are embedded in the command and subsequently recorded in the `PositionSizedEvent`, ensuring 100% deterministic reproducibility during historical replays without needing to reconstruct temporal market data.

## Decision 2: `VolatilityRiskPolicy` and Dynamic Stop Loss

We introduced `VolatilityRiskPolicy` which sizes a position such that a 1 ATR move scaled by a multiplier equals a specific fraction of the total equity.

**Rationale:**
* If the upstream Strategy does not explicitly define a `stop_loss_price`, this policy dynamically calculates one based on the entry price and the `ATR * multiplier`.
* The calculated dynamic stop loss is emitted via `SizingResult.dynamic_stop_loss` and carried in `PositionSizedEvent`.
* **Important Constraint:** The original `SizingRequest` is immutable and is not modified. Downstream systems (Execution Stage) can read the dynamic stop loss directly from the `PositionSizedEvent` or its wrapped envelope.

## Decision 3: `VolatilityTargetPolicy`

We introduced `VolatilityTargetPolicy` which scales the allocated capital based on the ratio of a Target Portfolio Annualized Volatility vs the Asset's Annualized Volatility.

**Rationale:**
* For M9B, we rely on the basic unadjusted formula: `Capital = Equity * (Target Vol / Asset Vol)`.
* Correlation matrices and covariance adjustments are explicitly excluded from M9B scope and deferred to M9C/M10 to prevent architectural bloat.

## Status

Approved for Implementation in M9B.
