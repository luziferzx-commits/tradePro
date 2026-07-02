import os
import shutil

base_dir = "models"
symbols = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

for symbol in symbols:
    cand_dir = os.path.join(base_dir, symbol, "candidate")
    prod_dir = os.path.join(base_dir, symbol, "production")
    if os.path.exists(cand_dir):
        os.makedirs(prod_dir, exist_ok=True)
        for version in os.listdir(cand_dir):
            src = os.path.join(cand_dir, version)
            dst = os.path.join(prod_dir, version)
            if not os.path.exists(dst):
                shutil.move(src, dst)
                print(f"Promoted {symbol} {version} to production!")
