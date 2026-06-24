import os

# Create folder structure for GQOS
folders = [
    "gqos/kernel/implementations",
    "tests/gqos/kernel",
    "benchmarks",
    "docs/adr",
    "docs/architecture"
]

for f in folders:
    os.makedirs(f, exist_ok=True)
    
print("Directories created.")
