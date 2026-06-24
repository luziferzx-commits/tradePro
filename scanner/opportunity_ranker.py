"""scanner/opportunity_ranker.py"""
import logging

logger = logging.getLogger(__name__)

class OpportunityRanker:
    @staticmethod
    def rank_and_filter(signals: list[dict], metadata_helper) -> tuple[list[dict], list[dict]]:
        approved = []
        rejected = []

        for sig in signals:
            symbol = sig.get('symbol')
            model_prob = sig.get('model_probability', 0.0)
            expected_r = sig.get('expected_r', 0.0)
            spread = sig.get('spread_points', 9999)
            vol_regime = sig.get('volatility_regime', 'NORMAL')
            
            # Fetch metadata
            max_spread = metadata_helper.get_spread_limit(symbol)
            liquidity = metadata_helper.get_liquidity_score(symbol)
            sig['liquidity_score'] = liquidity
            
            reject_reasons = []
            
            # Rejection conditions
            from config.settings import settings
            threshold = settings.GLOBAL_SIGNAL_THRESHOLD
            
            if model_prob < threshold:
                reject_reasons.append(f"Low model probability {model_prob:.2f} < {threshold}")
            if expected_r <= 0:
                reject_reasons.append(f"Expected R {expected_r:.2f} <= 0")
            if spread > max_spread:
                reject_reasons.append(f"Spread {spread} > Max {max_spread}")
            if liquidity < 0.5:
                reject_reasons.append(f"Low liquidity {liquidity}")
            if vol_regime == "EXTREME":
                reject_reasons.append("Extreme volatility regime")
                
            if reject_reasons:
                sig['status'] = 'REJECTED'
                sig['reason'] = " | ".join(reject_reasons)
                sig['final_score'] = 0.0
                rejected.append(sig)
            else:
                # Calculate final conservative score
                # Base score from probability
                score = model_prob * 100
                
                # Liquidity penalty
                score *= liquidity
                
                # Spread penalty (closer to max spread = lower score)
                spread_ratio = spread / max_spread if max_spread > 0 else 1.0
                score *= (1.0 - (spread_ratio * 0.5)) # Max 50% penalty for spread
                
                sig['status'] = 'APPROVED'
                sig['reason'] = 'Passed all filters'
                sig['final_score'] = round(score, 2)
                approved.append(sig)
                
        # Sort approved by final_score descending
        approved = sorted(approved, key=lambda x: x['final_score'], reverse=True)
        return approved, rejected
