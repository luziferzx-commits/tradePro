import os
import numpy as np
import pandas as pd
import glob
from sklearn.metrics.pairwise import cosine_similarity
from config.settings import settings
import logging

logger = logging.getLogger("GoldBot.MarketMemory")

class MarketMemory:
    def __init__(self, memory_file="models/memory_bank.npy"):
        self.memory_file = memory_file
        self.memory_vectors = None
        self.features = [
            "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
            "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
            "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
        ]
        self.load_memory()
        
    def load_memory(self):
        if os.path.exists(self.memory_file):
            self.memory_vectors = np.load(self.memory_file)
            logger.info(f"Loaded Market Memory: {len(self.memory_vectors)} winning trades.")
        else:
            logger.warning("Market Memory not found. Will rebuild on next call if needed.")
            
    def rebuild_memory(self):
        logger.info("Rebuilding Market Memory from latest dataset...")
        datasets = glob.glob("datasets/ml_volatility_expansion_atr_*_v*.csv")
        if not datasets:
            logger.error("No datasets found to build Market Memory.")
            return
            
        latest_dataset = sorted(datasets)[-1]
        df = pd.read_csv(latest_dataset)
        
        # Filter only winning trades
        winners = df[df['label'] == 1].copy()
        
        if winners.empty:
            logger.error("No winning trades found in dataset.")
            return
            
        # Extract features and convert to numpy array
        vectors = winners[self.features].to_numpy()
        
        # Standardize features (mean=0, std=1) for better cosine similarity
        # However, for true cosine similarity without full scaling, we can just use the raw features
        # since Scikit-Learn cosine_similarity normalizes the vectors.
        # But wait, feature scales are different (ADX 0-100, MACD tiny, ATR small).
        # We must scale them first.
        self.mean = np.mean(vectors, axis=0)
        self.std = np.std(vectors, axis=0)
        self.std[self.std == 0] = 1.0 # avoid div zero
        
        scaled_vectors = (vectors - self.mean) / self.std
        
        # Limit to Top 1000 winning trades (most recent)
        if len(scaled_vectors) > 1000:
            scaled_vectors = scaled_vectors[-1000:]
            
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        np.save(self.memory_file, scaled_vectors)
        np.save(self.memory_file.replace(".npy", "_mean.npy"), self.mean)
        np.save(self.memory_file.replace(".npy", "_std.npy"), self.std)
        
        self.memory_vectors = scaled_vectors
        logger.info(f"Market Memory rebuilt and saved with {len(self.memory_vectors)} vectors.")
        
    def get_similarity(self, features_dict):
        """
        Returns the max cosine similarity (0 to 1) to historical winning trades.
        """
        if self.memory_vectors is None:
            self.load_memory()
            if self.memory_vectors is None:
                self.rebuild_memory()
                if self.memory_vectors is None:
                    return 0.0
                    
        # Load mean/std
        try:
            mean = np.load(self.memory_file.replace(".npy", "_mean.npy"))
            std = np.load(self.memory_file.replace(".npy", "_std.npy"))
        except FileNotFoundError:
            self.rebuild_memory()
            mean = np.load(self.memory_file.replace(".npy", "_mean.npy"))
            std = np.load(self.memory_file.replace(".npy", "_std.npy"))
            
        # Build query vector
        query = np.array([features_dict.get(f, 0.0) for f in self.features])
        scaled_query = (query - mean) / std
        scaled_query = scaled_query.reshape(1, -1)
        
        # Calculate cosine similarity against all memory vectors
        sims = cosine_similarity(scaled_query, self.memory_vectors)[0]
        
        # Get the top similarity
        max_sim = np.max(sims)
        
        # Convert -1 to 1 range to 0 to 1
        max_sim = (max_sim + 1) / 2.0
        
        return float(max_sim)

market_memory = MarketMemory()
