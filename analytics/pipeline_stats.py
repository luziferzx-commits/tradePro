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
            "rejected_total": 0,
            
            # Shadow Testing Stats
            "prod_approve_count": 0,
            "candidate_approve_count": 0,
            "agreement_count": 0,
            "disagreement_count": 0,
            "candidate_only_signals": 0,
            "production_only_signals": 0,
            "simulated_orders_from_candidate": 0
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
            "min": 1.0,
            
            # Shadow Probabilities
            "prod_sum": 0.0,
            "prod_count": 0,
            "cand_sum": 0.0,
            "cand_count": 0
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
            
    def log_shadow(self, symbol, prod_approved, cand_approved, prod_prob, cand_prob):
        if prod_prob is not None:
            self.ml_probs["prod_sum"] += prod_prob
            self.ml_probs["prod_count"] += 1
            if prod_approved:
                self.stats["prod_approve_count"] += 1
                
        if cand_prob is not None:
            self.ml_probs["cand_sum"] += cand_prob
            self.ml_probs["cand_count"] += 1
            if cand_approved:
                self.stats["candidate_approve_count"] += 1
                
        if prod_prob is not None and cand_prob is not None:
            if prod_approved == cand_approved:
                self.stats["agreement_count"] += 1
            else:
                self.stats["disagreement_count"] += 1
                
            if cand_approved and not prod_approved:
                self.stats["candidate_only_signals"] += 1
            if prod_approved and not cand_approved:
                self.stats["production_only_signals"] += 1
                
    def log_simulated_order(self, from_candidate=False):
        self.stats["simulated_orders"] += 1
        if from_candidate:
            self.stats["simulated_orders_from_candidate"] += 1
            
    def print_summary(self, symbol="XAUUSDm"):
        logger.info(f"========== [Pipeline Stats {symbol}] ==========")
        logger.info(f"Candles Checked: {self.stats['candles_checked']}")
        logger.info(f"Quant Pass: {self.stats['quant_pass']}")
        logger.info(f"ML Pass: {self.stats['ml_pass']}")
        logger.info(f"Simulated Orders: {self.stats['simulated_orders']}")
        
        # Shadow Summary
        logger.info(f"\n[Shadow Testing Stats]")
        logger.info(f"Prod Approves: {self.stats['prod_approve_count']} | Cand Approves: {self.stats['candidate_approve_count']}")
        logger.info(f"Agreement: {self.stats['agreement_count']} | Disagreement: {self.stats['disagreement_count']}")
        logger.info(f"Cand Only Signals: {self.stats['candidate_only_signals']}")
        logger.info(f"Prod Only Signals: {self.stats['production_only_signals']}")
        logger.info(f"Sim Orders from Cand: {self.stats['simulated_orders_from_candidate']}")
        
        if self.ml_probs["prod_count"] > 0:
            avg_prod = self.ml_probs["prod_sum"] / self.ml_probs["prod_count"]
            logger.info(f"Average Prod Prob: {avg_prod:.4f}")
        if self.ml_probs["cand_count"] > 0:
            avg_cand = self.ml_probs["cand_sum"] / self.ml_probs["cand_count"]
            logger.info(f"Average Cand Prob: {avg_cand:.4f}")
            
        logger.info("\n[Reject Breakdown]")
        for k, v in self.reject_breakdown.items():
            if v > 0:
                logger.info(f"{k}: {v}")
        logger.info("===============================================")

pipeline_stats = PipelineStats()
