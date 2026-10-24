"""Calibrate the v1.3.2 recency check on development files only.

Run from the bundle folder after generating the development files:
    python semi_gen.py; python development/dev_pause_check.py; python development/make_dev.py
then: python development/recency_dev.py   (or development/recency_eval.py <threshold>)
"""
import os, sys, glob, pickle
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import hinigram_live as hl
from semi_gen import MACS, SCEN, PROFILE
from make_dev import DEV, DEPTHS
OLD = {"short7": [(0, 140, 16.0), (140, 147, 0), (147, 180, 16.0)], "short9": [(0, 40, 15.0), (40, 49, 0), (49, 180, 15.0)],
       "pause11": [(0, 35, 18.0), (35, 46, 0), (46, 180, 18.0)], "pause13": [(0, 145, 17.0), (145, 158, 0), (158, 180, 17.0)]}
files = []
for name, segs in SCEN.items():
    for seed in (1, 2):
        files.append((f"semi/{name}_s{seed}.csv", name, segs, PROFILE.get(name, "adult"), seed))
for name, segs in OLD.items():
    for seed in (3, 4):
        files.append((f"semi/{name}_s{seed}.csv", name, segs, "adult", seed))
for name, (segs, prof) in DEV.items():
    for seed in (5, 6):
        files.append((f"dev132/{name}_s{seed}.csv", name, segs, prof, seed))

def silence_run(segs, t_end, win=30.0):
    """seconds of programmed silence at the window end, and whether the whole window is breathing."""
    run = 0.0
    for a, b, r in segs:
        if r == 0 and a < t_end <= b + 1e-9:
            run = t_end - a
    any_pause = any(r == 0 and a < t_end and b > t_end - win for a, b, r in segs)
    return run, any_pause

def run(min_ratio, cache=None):
    rows = []
    for path, name, segs, prof, seed in files:
        S = hl.load_csi_session(path)
        cfg = hl.RRConfig(profile=prof, recent_min_ratio=min_ratio)
        tr = hl.analyze_session(S, cfg)
        for i, mac in enumerate(MACS):
            T = tr[mac]
            for j, t in enumerate(T.t):
                sr, anyp = silence_run(segs, float(t))
                rows.append(dict(file=os.path.basename(path), name=name, prof=prof, seed=seed, mac=mac[-2:], depth=DEPTHS[i], t=float(t),
                                 ratio=float(T.recent_ratio[j]), rel=bool(T.reliable[j]), mot=bool(T.motion[j]), status=T.status[j],
                                 reason=T.reason[j], silence=sr, any_pause=anyp))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    d = run(0.0)
    d.to_pickle("dev132/recency_off.pkl")
    pd.set_option("display.width", 200)
    br = d[~d.any_pause & d.rel]
    print("BREATHING windows shown (v1.3.1 reliable), ratio quantiles by depth")
    print(br.groupby("depth").ratio.describe(percentiles=[.01, .02, .05, .1, .5]).round(3).to_string())
    for th in (0.35, 0.4, 0.45, 0.5, 0.55):
        print(f"  share of breathing readings that a {th} threshold would withhold:", br.groupby("depth").ratio.apply(lambda v: round(float((v < th).mean()), 4)).to_dict())
    print("by profile/name at all depths, 5th pct:")
    print(br.groupby(["name"]).ratio.quantile(0.05).round(3).to_string())
    pz = d[(d.silence > 0)]
    pz = pz.assign(bin=pd.cut(pz.silence, [0, 3, 6, 9, 12, 16, 20, 30]))
    print("PAUSE windows: median ratio and share shown as reliable by v1.3.1, by silence-at-end bin and depth")
    print(pz.groupby(["depth", "bin"], observed=True).agg(n=("ratio", "size"), ratio_med=("ratio", "median"), ratio_q90=("ratio", lambda v: v.quantile(0.9)),
          v131_rel=("rel", "mean"), typical=("status", lambda s: (s == "typical").mean())).round(2).to_string())
