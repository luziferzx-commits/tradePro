import os

base_dir = "models"
symbols = []
for symbol in os.listdir(base_dir):
    prod_dir = os.path.join(base_dir, symbol, "production")
    if os.path.exists(prod_dir) and os.listdir(prod_dir):
        symbols.append(symbol)

print(f"Total production symbols: {len(symbols)}")
print("Symbols:", sorted(symbols))
