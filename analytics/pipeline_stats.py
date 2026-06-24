import logging

logger = logging.getLogger("GoldBot.PipelineStats")

class PipelineStats:
    def __init__(self):
        self.stats = {
            "candles_checked": 0,
            "indicators_pass": 0,
            "regime_pass": 0,
            "quant_pass": 0,
            "memory_pass": 0,
            "ml_pass": 0,
            "risk_pass": 0,
            "simulated_orders": 0,
            "rejected_total": 0
        }
        
        self.reject_breakdown = {
            "spread_too_high": 0,
            "indicators_failed": 0,
            "regime_rejected": 0,
            "quant_neutral": 0,
            "market_memory_rejected": 0,
            "ml_probability_too_low": 0,
            "ml_model_not_found": 0,
            "portfolio_risk_exceeded": 0,
            "circuit_breaker": 0,
            "news_filter": 0,
            "order_validation_failed": 0
        }
        
        self.ml_probs = {
            "sum": 0.0,
            "count": 0,
            "max": 0.0,
            "min": 1.0
        }
        
    def log_pass(self, stage):
        if stage in self.stats:
            self.stats[stage] += 1
            
    def log_reject(self, reason_key, symbol=None):
        self.stats["rejected_total"] += 1
        if reason_key in self.reject_breakdown:
            self.reject_breakdown[reason_key] += 1
        else:
            self.reject_breakdown[reason_key] = 1
            
    def log_ml_probability(self, prob):
        self.ml_probs["sum"] += prob
        self.ml_probs["count"] += 1
        if prob > self.ml_probs["max"]:
            self.ml_probs["max"] = prob
        if prob < self.ml_probs["min"]:
            self.ml_probs["min"] = prob
            
    def print_summary(self, symbol="XAUUSDm"):
        logger.info(f"========== [Pipeline Stats {symbol}] ==========")
        logger.info(f"Candles Checked: {self.stats['candles_checked']}")
        logger.info(f"Indicators Pass: {self.stats['indicators_pass']}")
        logger.info(f"Regime Pass: {self.stats['regime_pass']}")
        logger.info(f"Quant Pass: {self.stats['quant_pass']}")
        logger.info(f"Memory Pass: {self.stats['memory_pass']}")
        logger.info(f"ML Pass: {self.stats['ml_pass']}")
        logger.info(f"Risk Pass: {self.stats['risk_pass']}")
        logger.info(f"Simulated Orders: {self.stats['simulated_orders']}")
        
        if self.ml_probs["count"] > 0:
            avg_prob = self.ml_probs["sum"] / self.ml_probs["count"]
            logger.info(f"\n[ML Probability Stats]")
            logger.info(f"Average: {avg_prob:.4f}")
            logger.info(f"Max: {self.ml_probs['max']:.4f}")
            logger.info(f"Min: {self.ml_probs['min']:.4f}")
        
        logger.info("\n[Reject Breakdown]")
        for k, v in self.reject_breakdown.items():
            if v > 0:
                logger.info(f"{k}: {v}")
        logger.info("===============================================")

pipeline_stats = PipelineStats()
