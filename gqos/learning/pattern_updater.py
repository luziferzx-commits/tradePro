"""
gqos/learning/pattern_updater.py

Pattern Confidence Updater — อัปเดต PF ของ pattern แบบ Rolling
ทำให้ pattern database สะท้อนความเป็นจริงของตลาดปัจจุบัน

Algorithm:
  new_pf = (historical_pf × decay) + (live_pf × (1 - decay))
  decay = 0.7 → historical มีน้ำหนัก 70%, live 30%
  เมื่อมี live trades มากขึ้น → live weight เพิ่มขึ้น
"""
import logging
import os
from datetime import datetime
import pandas as pd
import numpy as np
from config.settings import settings

logger = logging.getLogger("GQOS.PatternUpdater")

PATTERN_DB_PATH = "data/pattern_store/pattern_database.parquet"
BACKUP_PATH = "data/pattern_store/pattern_database.BACKUP.parquet"


class PatternConfidenceUpdater:
    """
    อัปเดต confidence ของ patterns ตาม live trading outcomes
    """

    def __init__(
        self,
        historical_weight: float = 0.7,
        min_live_trades: int = 5,
        allowed_sources: str | None = None,
    ):
        """
        historical_weight: น้ำหนัก historical data (0.7 = 70%)
        min_live_trades: จำนวน live trades ขั้นต่ำก่อนจะ update pattern
        """
        self.historical_weight = historical_weight
        self.live_weight = 1.0 - historical_weight
        self.min_live_trades = min_live_trades
        raw_sources = allowed_sources or settings.LEARNING_ALLOWED_SOURCES
        self.allowed_sources = {s.strip().upper() for s in str(raw_sources).split(",") if s.strip()}
        self.auto_demote_live_pf_threshold = settings.AUTO_DEMOTE_LIVE_PF_THRESHOLD
        self.auto_demote_min_live_trades = settings.AUTO_DEMOTE_MIN_LIVE_TRADES

    def update(self, outcomes_df: pd.DataFrame) -> dict:
        """
        รับ live outcomes แล้วอัปเดต pattern database

        Returns: summary ของ patterns ที่ถูก update
        """
        if outcomes_df.empty or "pattern_id" not in outcomes_df.columns:
            logger.info("[PatternUpdater] No outcomes to process.")
            return {"updated": 0, "skipped": 0}

        if "source" in outcomes_df.columns:
            before = len(outcomes_df)
            outcomes_df = outcomes_df[
                outcomes_df["source"].fillna("LIVE").astype(str).str.upper().isin(self.allowed_sources)
            ]
            logger.info("[PatternUpdater] Source filter kept %s/%s outcome rows.", len(outcomes_df), before)
            if outcomes_df.empty:
                return {"updated": 0, "skipped": 0}

        if not os.path.exists(PATTERN_DB_PATH):
            logger.error(f"[PatternUpdater] Pattern DB not found: {PATTERN_DB_PATH}")
            return {"updated": 0, "skipped": 0}

        # Backup ก่อน
        df_patterns = pd.read_parquet(PATTERN_DB_PATH)
        df_patterns.to_parquet(BACKUP_PATH)
        logger.info(f"[PatternUpdater] Backup saved: {BACKUP_PATH}")

        # คำนวณ live stats per pattern
        live_stats = self._compute_live_stats(outcomes_df)

        updated = 0
        skipped = 0
        pending_promotions = []

        for pattern_id, stats in live_stats.items():
            if stats["n"] < self.min_live_trades:
                skipped += 1
                continue

            mask = df_patterns["pattern_id"] == pattern_id
            if not mask.any():
                skipped += 1
                continue

            old_pf = float(df_patterns.loc[mask, "profit_factor"].iloc[0])
            old_wr = float(df_patterns.loc[mask, "win_rate"].iloc[0])

            # Bayesian Edge Decay
            prior_n = 50
            prior_wins = old_wr * prior_n
            
            total_n = prior_n + stats["n"]
            new_wr = (prior_wins + stats["wins"]) / total_n
            
            # For profit factor, we use a simple weighted average based on sample sizes
            new_pf = (old_pf * prior_n + stats["pf"] * stats["n"]) / total_n

            df_patterns.loc[mask, "profit_factor"] = round(new_pf, 4)
            df_patterns.loc[mask, "win_rate"] = round(new_wr, 4)
            df_patterns.loc[mask, "occurrences"] = (
                df_patterns.loc[mask, "occurrences"] + stats["n"]
            )

            old_status = df_patterns.loc[mask, "promotion_status"].iloc[0]
            
            # Re-evaluate promotion status
            if (
                str(old_status) == "LIVE_APPROVED"
                and stats["n"] >= self.auto_demote_min_live_trades
                and stats["pf"] < self.auto_demote_live_pf_threshold
            ):
                new_status_eval = "SHADOW_PASSED"
                logger.warning(
                    "[PatternUpdater] Auto-demoting %s from LIVE_APPROVED: live PF %.2f < %.2f over %s trades",
                    pattern_id,
                    stats["pf"],
                    self.auto_demote_live_pf_threshold,
                    stats["n"],
                )
            elif stats["n"] >= self.auto_demote_min_live_trades and stats["pf"] < 0.85:
                new_status_eval = "DEMOTED"
                logger.warning(
                    "[PatternUpdater] Auto-demoting %s: live PF %.2f over %s trades",
                    pattern_id,
                    stats["pf"],
                    stats["n"],
                )
            else:
                new_status_eval = self._evaluate_promotion(
                    new_pf, new_wr, int(df_patterns.loc[mask, "occurrences"].iloc[0]), str(old_status)
                )
            
            if new_status_eval == "PENDING_APPROVAL":
                pending_promotions.append({
                    "pattern_id": pattern_id,
                    "old_pf": old_pf,
                    "new_pf": new_pf,
                    "win_rate": new_wr,
                    "n": total_n
                })
                # Leave old status in place until confirmed
            else:
                df_patterns.loc[mask, "promotion_status"] = new_status_eval

            updated += 1
            logger.info(
                f"[PatternUpdater] {pattern_id}: "
                f"PF {old_pf:.2f}→{new_pf:.2f} "
                f"WR {old_wr:.1%}→{new_wr:.1%} "
                f"(live n={stats['n']})"
            )

        # Save updated DB
        df_patterns.to_parquet(PATTERN_DB_PATH)
        logger.info(
            f"[PatternUpdater] Done. Updated={updated}, Skipped={skipped}, Pending={len(pending_promotions)}"
        )
        return {"updated": updated, "skipped": skipped, "pending_promotions": pending_promotions}

    def _compute_live_stats(self, df: pd.DataFrame) -> dict:
        """คำนวณสถิติต่อ pattern จาก live outcomes"""
        stats = {}
        for pattern_id, group in df.groupby("pattern_id"):
            if pd.isna(pattern_id):
                continue
            wins = len(group[group["outcome"] == "WIN"])
            losses = len(group[group["outcome"] == "LOSS"])
            n = len(group)
            win_rate = wins / n if n > 0 else 0.0

            gross_win = group[group["outcome"] == "WIN"]["realized_pnl"].sum()
            gross_loss = abs(group[group["outcome"] == "LOSS"]["realized_pnl"].sum())
            pf = gross_win / gross_loss if gross_loss > 0 else (2.0 if wins > 0 else 0.5)

            stats[pattern_id] = {
                "n": n,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "pf": round(pf, 4),
            }
        return stats

    def _evaluate_promotion(self, pf: float, win_rate: float, n: int, old_status: str) -> str:
        """Re-evaluate promotion status based on updated metrics"""
        if pf < 0.8 and n >= 20:
            return "DEMOTED"
        if pf >= 1.3 and win_rate >= 0.45 and n >= 50:
            if old_status != "LIVE_APPROVED":
                return "PENDING_APPROVAL"
            return "LIVE_APPROVED"
        if pf >= 1.2 and n >= 20:
            return "SHADOW_PASSED"
        if pf >= 1.1 and n >= 10:
            return "RESEARCH_VALIDATED"
        if pf >= 1.0 and n >= 5:
            return "RESEARCH_DISCOVERED"
        return "REJECTED"


# Singleton
pattern_updater = PatternConfidenceUpdater()
