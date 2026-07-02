import os
import numpy as np
import pandas as pd
import glob
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger("GoldBot.MarketMemory")

class MarketMemory:
    def __init__(self):
        self.memory_cache = {}
        self.features = [
            "final_score", "trend_score", "breakout_score", "reversal_score", "session_score",
            "atr", "adx", "ema50_slope", "rsi", "macd", "hour_utc",
            "is_high_volatility", "is_buy", "recent_high_20_distance", "recent_low_20_distance"
        ]
        
    def get_memory_file(self, symbol):
        return f"models/memory_bank_{symbol}.npy"

    def load_memory(self, symbol):
        mem_file = self.get_memory_file(symbol)
        if os.path.exists(mem_file):
            self.memory_cache[symbol] = np.load(mem_file)
            logger.info(f"Loaded Market Memory for {symbol}: {len(self.memory_cache[symbol])} winning trades.")
        else:
            logger.warning(f"Market Memory not found for {symbol}. Will attempt to rebuild.")
            self.memory_cache[symbol] = None
            
    def rebuild_memory(self, symbol):
        logger.info(f"Rebuilding Market Memory for {symbol}...")
        
        # Look for symbol specific datasets
        datasets = glob.glob(f"datasets/*{symbol}*.csv")
        
        # Fallback for old naming convention if it's XAUUSD/XAUUSDm
        if not datasets and "XAU" in symbol:
            datasets = glob.glob("datasets/ml_volatility_expansion_atr_*_v*.csv")
            
        if not datasets:
            logger.warning(f"No datasets found to build Market Memory for {symbol}.")
            return
            
        latest_dataset = sorted(datasets)[-1]
        df = pd.read_csv(latest_dataset)
        
        # Filter only winning trades
        if 'label' not in df.columns:
            logger.error(f"Dataset {latest_dataset} missing 'label' column.")
            return
            
        winners = df[df['label'] == 1].copy()
        
        if winners.empty:
            logger.warning(f"No winning trades found in dataset for {symbol}.")
            return
            
        # Extract features and convert to numpy array
        try:
            vectors = winners[self.features].to_numpy()
        except KeyError as e:
            logger.error(f"Dataset missing required features: {e}")
            return
        
        mean = np.mean(vectors, axis=0)
        std = np.std(vectors, axis=0)
        std[std == 0] = 1.0 # avoid div zero
        
        scaled_vectors = (vectors - mean) / std
        
        # Limit to Top 1000 winning trades (most recent)
        if len(scaled_vectors) > 1000:
            scaled_vectors = scaled_vectors[-1000:]
            
        mem_file = self.get_memory_file(symbol)
        os.makedirs(os.path.dirname(mem_file), exist_ok=True)
        
        np.save(mem_file, scaled_vectors)
        np.save(mem_file.replace(".npy", "_mean.npy"), mean)
        np.save(mem_file.replace(".npy", "_std.npy"), std)
        
        self.memory_cache[symbol] = scaled_vectors
        logger.info(f"Market Memory for {symbol} rebuilt and saved with {len(scaled_vectors)} vectors.")
        
    def get_similarity(self, symbol, features_dict):
        """
        Returns the max cosine similarity (0 to 1) to historical winning trades for the specific symbol.
        """
        if symbol not in self.memory_cache:
            self.load_memory(symbol)
            if self.memory_cache.get(symbol) is None:
                self.rebuild_memory(symbol)
                if self.memory_cache.get(symbol) is None:
                    return 0.0
                    
        mem_file = self.get_memory_file(symbol)
        
        # Load mean/std
        try:
            mean = np.load(mem_file.replace(".npy", "_mean.npy"))
            std = np.load(mem_file.replace(".npy", "_std.npy"))
        except FileNotFoundError:
            self.rebuild_memory(symbol)
            if self.memory_cache.get(symbol) is None:
                return 0.0
            mean = np.load(mem_file.replace(".npy", "_mean.npy"))
            std = np.load(mem_file.replace(".npy", "_std.npy"))
            
        # Build query vector
        query = np.array([features_dict.get(f, 0.0) for f in self.features])
        scaled_query = (query - mean) / std
        scaled_query = scaled_query.reshape(1, -1)
        
        memory_vectors = self.memory_cache[symbol]
        
        if memory_vectors is None or len(memory_vectors) == 0:
            return 0.0
            
        # Calculate cosine similarity against all memory vectors
        sims = cosine_similarity(scaled_query, memory_vectors)[0]
        
        # Get the top similarity
        max_sim = np.max(sims)
        
        # Convert -1 to 1 range to 0 to 1
        max_sim = (max_sim + 1) / 2.0
        
        return float(max_sim)

market_memory = MarketMemory()
