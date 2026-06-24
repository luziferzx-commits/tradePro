import os
import hashlib
import json
import psutil
from datetime import datetime

class BaselineHasher:
    def __init__(self, output_file="baseline_hash.txt"):
        self.output_file = output_file
        self.directories = ["main.py", "strategy", "risk", "ml", "config"]
        
    def hash_file(self, filepath):
        hasher = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                buf = f.read()
                hasher.update(buf)
            return hasher.hexdigest()
        except Exception:
            return None
            
    def generate_hashes(self):
        print("Generating baseline SHA256 hashes...")
        hashes = {}
        for item in self.directories:
            if os.path.isfile(item):
                h = self.hash_file(item)
                if h: hashes[item] = h
            elif os.path.isdir(item):
                for root, _, files in os.walk(item):
                    for file in files:
                        if file.endswith('.py') or file.endswith('.json') or file.endswith('.yaml'):
                            filepath = os.path.join(root, file)
                            h = self.hash_file(filepath)
                            if h: hashes[filepath] = h
                            
        with open(self.output_file, 'w') as f:
            for filepath, h in sorted(hashes.items()):
                f.write(f"{h}  {filepath}\n")
        print(f"Hashes saved to {self.output_file}")

class SystemSnapshot:
    def __init__(self, output_dir="artifacts"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate(self):
        date_str = datetime.utcnow().strftime("%Y%m%d")
        output_file = os.path.join(self.output_dir, f"system_snapshot_{date_str}.json")
        
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        sqlite_size = 0
        if os.path.exists("trades.db"):
            sqlite_size = os.path.getsize("trades.db") / (1024*1024)
            
        logs_size = 0
        if os.path.exists("goldbot.log"):
            logs_size = os.path.getsize("goldbot.log") / (1024*1024)
            
        snapshot = {
            "cpu": cpu,
            "ram_mb": ram.used / (1024*1024),
            "disk_free_gb": disk.free / (1024*1024*1024),
            "sqlite_size_mb": round(sqlite_size, 2),
            "logs_size_mb": round(logs_size, 2),
            "feature_rows": 0, # Placeholder, can be queried from DB if needed
            "shadow_trades": 0 # Placeholder
        }
        
        with open(output_file, 'w') as f:
            json.dump(snapshot, f, indent=4)
            
        print(f"System snapshot saved to {output_file}")

if __name__ == "__main__":
    hasher = BaselineHasher()
    hasher.generate_hashes()
    
    snapshot = SystemSnapshot()
    snapshot.generate()
