"""Held-out set 4 (fresh seeds 41-42), run once after v1.3.2 was frozen (sha256 in frozen_hash_v132.txt).

Same eleven scenarios as held-out set 3, so v1.3.1 (set 3) and v1.3.2 (set 4) can be compared:
the eight base scenarios of validate_heldout.py plus an 8 s pause (negative control, must not be
flagged), a 14 s adult pause and a 25 s pause in a child (pediatric threshold 20 s).
"""
import json, os, sys, time, hashlib
import numpy as np
import hinigram_live as hl
import legacy_v12 as L
from validate_pipelines import legacy_window, LEGACY_TO_STATUS
from validate_heldout import HELD as HELD_BASE, DEPTHS, MACS, SRC, WIN, truth_status, nearest_boundary_gap

assert hashlib.sha256(open("hinigram_live.py", "rb").read()).hexdigest() == open("frozen_hash_v132.txt").read().split()[0], "code changed after freezing"
HELD = dict(HELD_BASE)
HELD.update({
    "short_8s": ([(0, 150, 16.0), (150, 158, 0), (158, 180, 16.0)], "adult"),
    "pause_14s": ([(0, 120, 17.0), (120, 134, 0), (134, 180, 17.0)], "adult"),
    "child_pause_25s": ([(0, 130, 30.0), (130, 155, 0), (155, 180, 30.0)], "child_1_5y"),
})

if __name__ == "__main__":
    SEEDS = [41, 42]
    OUT = "heldout4_rows.json"
    os.makedirs("semi_heldout4", exist_ok=True)
    t0 = time.time(); rows = []
    for seed in SEEDS:
        for name, (segs, prof) in HELD.items():
            scs = {m: hl.BreathingScenario(segs, depth=d, phase_depth=d, seed=seed * 10 + i, name=name) for i, (m, d) in enumerate(zip(MACS, DEPTHS))}
            path = f"semi_heldout4/{name}_s{seed}.csv"
            if not os.path.exists(path):
                hl.inject_breathing(SRC, path, scs)
            S = hl.load_csi_session(path)
            tracks = hl.analyze_session(S, hl.RRConfig(profile=prof))
            leg = L.load_pjdsc_session(path)
            for mac in MACS:
                T = tracks[mac]
                truth = hl.truth_on_grid(scs[mac], T.t, WIN)
                for i, te in enumerate(T.t):
                    lb, lplv, ltier = legacy_window(leg[mac], te)
                    rows.append(dict(scenario=name, seed=seed, profile=prof, mac=mac, depth=scs[mac].depth, t=float(te), truth=float(truth[i]),
                                     truth_status=truth_status(scs[mac], te, prof), boundary_gap=nearest_boundary_gap(float(truth[i]), prof),
                                     new_bpm=float(T.bpm[i]), new_raw=float(T.bpm_raw[i]), new_reliable=bool(T.reliable[i]), new_status=T.status[i],
                                     new_reason=T.reason[i], new_motion=bool(T.motion[i]), new_pause=float(T.pause_s[i]), new_pause_est=float(T.pause_est[i]), new_recent=float(T.recent_ratio[i]),
                                     legacy_bpm=lb, legacy_plv=lplv, legacy_status=LEGACY_TO_STATUS.get(ltier, ltier)))
            print(f"{name} s{seed} {time.time() - t0:.0f}s", flush=True)
    S = hl.load_csi_session(SRC)
    tracks = hl.analyze_session(S, hl.RRConfig(profile="adult"))
    leg = L.load_pjdsc_session(SRC)
    for mac in MACS:
        T = tracks[mac]
        for i, te in enumerate(T.t):
            lb, lplv, ltier = legacy_window(leg[mac], te)
            rows.append(dict(scenario="raw_sample_null", seed=0, profile="adult", mac=mac, depth=0.0, t=float(te), truth=float("nan"), truth_status="absent",
                             boundary_gap=float("nan"), new_bpm=float(T.bpm[i]), new_raw=float(T.bpm_raw[i]), new_reliable=bool(T.reliable[i]),
                             new_status=T.status[i], new_reason=T.reason[i], new_motion=bool(T.motion[i]), new_pause=float(T.pause_s[i]),
                             new_pause_est=float(T.pause_est[i]), legacy_bpm=lb, legacy_plv=lplv, legacy_status=LEGACY_TO_STATUS.get(ltier, ltier)))
    json.dump(rows, open(OUT, "w"))
    print("rows", len(rows), "time %.0fs" % (time.time() - t0))
