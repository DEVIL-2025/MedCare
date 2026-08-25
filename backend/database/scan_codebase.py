import os
import re
import sys
import io

# Pylance-safe UTF-8 configuration
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")

frontend_dir = r"e:\medcare-pharma-control-tower-main\medcare-frontend\src"
backend_dir = r"e:\medcare-pharma-control-tower-main\backend"

print("--- SCANNING FOR MOCK FILES & DATA IN FRONTEND ---")
for root, dirs, files in os.walk(frontend_dir):
    for f in files:
        if f.endswith(('.js', '.jsx', '.json')):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                txt = fp.read()
                if "mock" in txt.lower():
                    print(f"File {f} contains word 'mock'")
                if "Math.random" in txt:
                    print(f"File {f} contains 'Math.random'")

print("\n--- SCANNING DATA DIRECTORIES ---")
data_dir = os.path.join(frontend_dir, "data")
if os.path.exists(data_dir):
    print("Files in frontend/src/data:")
    for f in os.listdir(data_dir):
        print(f"  - {f}")

