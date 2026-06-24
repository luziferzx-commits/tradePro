import pytest
import time
import os
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from gqos.live.resilience import TokenBucket, RequestError, retry_policy
from gqos.live.metadata import MetadataCache
from gqos.ops.execution_quality import ExecutionQualityReport
from gqos.common.enums import TradeDirection
from prometheus_client import REGISTRY

# 1. Resilience Tests
def test_token_bucket_exhaustion_and_refill():
    bucket = TokenBucket(capacity=2, fill_rate=10.0)
    
    # Consume 2 tokens
    assert bucket.consume(1) == True
    assert bucket.consume(1) == True
    
    # Bucket exhausted
    assert bucket.consume(1) == False
    
    # Refill
    time.sleep(0.15) # Should add 1.5 tokens
    assert bucket.consume(1) == True

def test_retry_policy_400_fail_fast():
    @retry_policy(max_retries=2, base_delay=0.01)
    def failing_call():
        raise RequestError(400, "Bad Request")
        
    with pytest.raises(RequestError):
        failing_call()

def test_retry_policy_401_kill_switch():
    kill_switch_triggered = False
    def kill_switch(msg):
        nonlocal kill_switch_triggered
        kill_switch_triggered = True
        
    @retry_policy(max_retries=2, base_delay=0.01, kill_switch_callback=kill_switch)
    def failing_call():
        raise RequestError(401, "Unauthorized")
        
    with pytest.raises(RequestError):
        failing_call()
        
    assert kill_switch_triggered == True

def test_retry_policy_500_exponential_backoff():
    attempts = 0
    @retry_policy(max_retries=2, base_delay=0.01)
    def failing_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RequestError(500, "Internal Server Error")
        return "SUCCESS"
        
    assert failing_call() == "SUCCESS"
    assert attempts == 3

# 2. Metadata Cache Tests
@patch('requests.get')
def test_binance_exchangeInfo_parsing(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.10000000"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.00100000"},
                    {"filterType": "NOTIONAL", "minNotional": "10.00000000"}
                ]
            }
        ]
    }
    mock_get.return_value = mock_response
    
    cache = MetadataCache()
    cache.refresh()
    
    rules = cache.get_rules("BTCUSDT")
    assert rules is not None
    assert rules["tick_size"] == Decimal("0.1")
    assert rules["step_size"] == Decimal("0.001")
    assert rules["min_notional"] == Decimal("10.0")

# 3. Execution Quality Tests
def test_execution_quality_slippage():
    report_file = "test_reports/execution_report.jsonl"
    if os.path.exists(report_file):
        os.remove(report_file)
        
    analyzer = ExecutionQualityReport(log_dir="test_reports")
    
    # Arrival price = 100.0, Target qty = 10
    analyzer.register_order("ORD-1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('10.0'))
    
    # Partial fills
    analyzer.record_fill("ORD-1", Decimal('5.0'), Decimal('101.0')) # 5 qty @ 101
    analyzer.record_fill("ORD-1", Decimal('5.0'), Decimal('102.0')) # 5 qty @ 102
    
    # VWAP = 101.5
    # Arrival = 100.0
    # Slippage (Buy) = (101.5 - 100.0) / 100.0 * 10000 = 150 BPS
    
    with open(report_file, 'r') as f:
        data = json.loads(f.readline())
        
    assert data["order_id"] == "ORD-1"
    assert data["fill_vwap"] == 101.5
    assert data["slippage_bps"] == 150.0
    
    # Check Prometheus histogram registration
    samples = [s.name for m in REGISTRY.collect() for s in m.samples]
    assert "gqos_slippage_bps_sum" in samples

if __name__ == "__main__":
    pytest.main(["-v", __file__])
