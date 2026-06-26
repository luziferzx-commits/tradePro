import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import yaml
import argparse
import logging
from data.mt5_client import mt5_client
from ml.dataset_builder import build_dataset
from mlops.train_production import train_and_register_production
from ml.market_memory import market_memory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TrainAllMarkets")

def load_symbols(config_path="config/symbols.yaml"):
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load symbols: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description="Multi-Market Auto Training Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Run without actually saving models over production")
    parser.add_argument("--skip-xauusd", action="store_true", help="Skip XAUUSDm to preserve existing model")
    parser.add_argument("--candidate-only", action="store_true", help="Save models as candidate instead of production")
    parser.add_argument("--candles", type=int, default=200000, help="Number of candles to fetch for dataset building")
    parser.add_argument("--symbols", nargs="+", help="List of specific symbols to train (e.g., --symbols XAUUSDm BTCUSDm)")
    args = parser.parse_args()

    symbols_config = load_symbols().get('symbols', {})
    
    if args.symbols:
        # Filter config to only include requested symbols
        symbols_config = {k: v for k, v in symbols_config.items() if k in args.symbols}
        logger.info(f"Filtered to run only on: {args.symbols}")
    
    if not mt5_client.connect():
        logger.error("Failed to connect to MT5. Aborting pipeline.")
        return

    for symbol, cfg in symbols_config.items():
        if symbol == "symbol_aliases":
            continue
            
        if not cfg.get("enabled", False) and not args.dry_run:
            # Maybe we still want to train even if disabled? 
            # The user said "AI สร้าง Dataset + Train Model ของอีก 10 ตลาดไปพร้อมกัน พอวันไหนอยากเปิด ค่อยเปลี่ยน enabled: true"
            # So we should train regardless of 'enabled' flag!
            pass
            
        if args.skip_xauusd and "XAU" in symbol:
            logger.info(f"Skipping {symbol} as requested.")
            continue
            
        logger.info(f"--- Starting Pipeline for {symbol} ---")
        
        # 1. Build Dataset
        timeframe = cfg.get("timeframe", "M5")
        try:
            logger.info(f"Building dataset for {symbol}...")
            dataset_path = build_dataset(symbol, timeframe, atr_multiplier=2.0, max_candles=args.candles)
            if not dataset_path or not os.path.exists(dataset_path):
                logger.error(f"Failed to generate dataset for {symbol}. Skipping.")
                continue
        except Exception as e:
            logger.error(f"Error building dataset for {symbol}: {e}")
            continue
            
        # 2. Train Model
        status = "candidate" if (args.dry_run or args.candidate_only) else "production"
        try:
            logger.info(f"Training model for {symbol} (Status: {status})...")
            version = train_and_register_production(symbol, dataset_path, status)
            if not version:
                logger.error(f"Model training failed for {symbol}.")
                continue
        except Exception as e:
            logger.error(f"Error training model for {symbol}: {e}")
            continue
            
        # 3. Build Market Memory
        try:
            logger.info(f"Rebuilding Market Memory for {symbol}...")
            market_memory.rebuild_memory(symbol)
        except Exception as e:
            logger.error(f"Error building memory for {symbol}: {e}")
            continue
            
        logger.info(f"--- Completed Pipeline for {symbol} ---")

    mt5_client.disconnect()
    logger.info("All selected markets have been processed.")

if __name__ == "__main__":
    main()
