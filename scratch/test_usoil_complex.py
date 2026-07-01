import MetaTrader5 as mt5
import math

def main():
    if not mt5.initialize():
        print("Fail")
        return
    sym_info = mt5.symbol_info("USOILm")
    if sym_info is None:
        print("No USOILm")
        return
    
    vol_step = float(sym_info.volume_step)
    requested_volume = 0.01
    risk_multiplier = 1.0
    raw_volume = requested_volume * risk_multiplier
    volume = math.floor(raw_volume / vol_step) * vol_step
    volume = round(volume, 8)
    min_vol = float(sym_info.volume_min)
    
    print(f"vol_step: {vol_step} (type: {type(vol_step)})")
    print(f"volume: {volume} (type: {type(volume)})")
    print(f"min_vol: {min_vol} (type: {type(min_vol)})")
    print(f"volume < min_vol: {volume < min_vol}")
    
    mt5.shutdown()

if __name__ == '__main__':
    main()
