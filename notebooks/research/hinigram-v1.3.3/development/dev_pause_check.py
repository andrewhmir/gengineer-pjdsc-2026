"""Development check of the pause detector (v1.3.0 against the current pipeline) on dev files only (seeds 1-4, demo).

Written while building v1.3.1. Run from the bundle folder after `python semi_gen.py`; it creates the extra
short-pause files in semi/ when they are missing. `hinigram_live` is now v1.3.2.
"""
import os, sys, numpy as np
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "history"))
import hinigram_live as new
import hinigram_live_v130 as old
from semi_gen import MACS, SRC

DEPTHS = [0.06, 0.035, 0.02]
def ensure(name, segs, seed, prof="adult"):
    path = f"semi/{name}_s{seed}.csv"
    if not os.path.exists(path):
        scs = {m: new.BreathingScenario(segs, depth=d, phase_depth=d, seed=seed * 10 + i, name=name) for i, (m, d) in enumerate(zip(MACS, DEPTHS))}
        new.inject_breathing(SRC, path, scs)
    return path

cases = []
# dev pause scenario from semi_gen (17 s pause at 125 s), seeds 1-2
for seed in (1, 2):
    cases.append((f"semi/pause_s{seed}.csv", [(125, 142)], "adult", "pause 17 s"))
# negative controls: short pauses that must NOT be flagged (talking, swallowing)
for seed in (3, 4):
    # pauses placed where the real recording has no movement (about 30-60 s and 115-170 s)
    cases.append((ensure("short7", [(0, 140, 16.0), (140, 147, 0), (147, 180, 16.0)], seed), [(140, 147)], "adult", "short 7 s"))
    cases.append((ensure("short9", [(0, 40, 15.0), (40, 49, 0), (49, 180, 15.0)], seed), [(40, 49)], "adult", "short 9 s"))
    cases.append((ensure("pause11", [(0, 35, 18.0), (35, 46, 0), (46, 180, 18.0)], seed), [(35, 46)], "adult", "pause 11 s"))
    cases.append((ensure("pause13", [(0, 145, 17.0), (145, 158, 0), (158, 180, 17.0)], seed), [(145, 158)], "adult", "pause 13 s"))
# no-pause dev scenarios for false alarms
for nm in ("normal_to_fast", "fast_watch", "slow"):
    for seed in (1, 2):
        cases.append((f"semi/{nm}_s{seed}.csv", [], "adult", nm))
cases.append(("semi/demo_semisynthetic.csv", [(125, 142)], "adult", "demo"))

def summarize(mod, path, pauses, prof):
    S = mod.load_csi_session(path)
    tr = mod.analyze_session(S, mod.RRConfig(profile=prof))
    res = []
    for i, mac in enumerate(MACS):
        T = tr[mac]
        st = np.array(T.status); t = T.t
        urg = np.array([s_ == "urgent" and r_.startswith("Possible breathing pause") for s_, r_ in zip(T.status, T.reason)])
        if pauses:
            a, b = pauses[0]
            hit = np.where(urg & (t >= a) & (t <= b + 30))[0]
            lat = float(t[hit[0]] - a) if len(hit) else None
            false_u = int(np.sum(urg & ((t < a) | (t > b + 30))))
            # time back to non-urgent after the pause ends
            after = np.where((t > b) & ~urg)[0]
            rec = float(t[after[0]] - b) if len(hit) and len(after) else None
        else:
            lat, false_u, rec = None, int(urg.sum()), None
        res.append((DEPTHS[i] if "demo" not in path else [0.05, 0.05, 0.05][i], lat, false_u, rec))
    return res

for path, pauses, prof, label in cases:
    o = summarize(old, path, pauses, prof); n = summarize(new, path, pauses, prof)
    fmt = lambda r: " | ".join(f"{d*100:.1f}%: lat={'-' if l is None else f'{l:4.1f}'} fa={fa} rec={'-' if rc is None else f'{rc:4.1f}'}" for d, l, fa, rc in r)
    print(f"{label:16s} {os.path.basename(path):26s}\n   v1.3.0  {fmt(o)}\n   v1.3.1  {fmt(n)}")
