"""Run the development files with one recency threshold: python development/recency_eval.py 0.45 (from the bundle folder)."""
import sys, os, time
sys.path.insert(0, os.path.abspath(".")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("dev132", exist_ok=True)
import pandas as pd
from recency_dev import run
th = float(sys.argv[1]); t = time.time()
d = run(th); d.to_pickle(f"dev132/recency_{th:.2f}.pkl"); print(th, f"{time.time()-t:.0f}s")
