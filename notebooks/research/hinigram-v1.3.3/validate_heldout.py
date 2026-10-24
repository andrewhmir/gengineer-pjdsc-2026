"""Held-out semi-synthetic validation of v1.3 vs v1.2 (run once, after v1.3 thresholds were frozen).

Development data (used while building v1.3): scenarios in semi_gen.SCEN, seeds 1-2, depths 6/3.5/2 %.
Held-out data (this script): different rates, pause timings, ages, depths (5/3/1.5 %) and seeds (11-12).
Every file is the real 173 s format sample from the three ESP32 nodes with breathing of known
rate modulated onto its packets (loss, timing jitter, int8 quantisation and AGC gain steps kept).
"""
import json, os, time
import numpy as np
import hinigram_live as hl
import legacy_v12 as L
from validate_pipelines import legacy_window, LEGACY_TO_STATUS

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_20261019_024431.csv")
MACS = ["1a:00:00:00:00:01", "1a:00:00:00:00:02", "1a:00:00:00:00:03"]
WIN = 30.0
HELD = {
    # name: (segments, profile)
    "adult_10":   ([(0, 180, 10.0)], "adult"),
    "adult_17":   ([(0, 180, 17.0)], "adult"),
    "adult_23":   ([(0, 180, 23.0)], "adult"),
    "adult_32":   ([(0, 180, 32.0)], "adult"),
    "pause_12s":  ([(0, 140, 16.0), (140, 152, 0), (152, 180, 16.0)], "adult"),
    "pause_18s":  ([(0, 40, 18.0), (40, 58, 0), (58, 180, 18.0)], "adult"),
    "infant_55":  ([(0, 180, 55.0)], "infant_2_12m"),
    "child_34":   ([(0, 180, 34.0)], "child_1_5y"),
}
DEPTHS = [0.05, 0.03, 0.015]


def truth_status(sc, t_end, profile):
    tg = np.arange(max(0, t_end - WIN), t_end + 1e-9, 0.05)
    _, bpm = hl.breathing_waveform(tg, sc)
    pause_min = 10.0 if profile == "adult" else 20.0
    run = 0.0
    for v in bpm[::-1]:
        if v > 0:
            break
        run += 0.05
    if run >= pause_min:
        return "urgent"
    seg = bpm[bpm > 0]
    if len(seg) < 0.8 * len(bpm):
        return "transition"
    return hl.classify_rate(float(np.mean(seg)), profile)[0]


def nearest_boundary_gap(bpm, profile):
    if not np.isfinite(bpm):
        return np.nan
    cuts = {"adult": [8.5, 11.5, 20.5, 24.5], "child_1_5y": [15, 40], "infant_2_12m": [20, 50],
            "newborn_lt2m": [25, 60]}[profile]
    return float(min(abs(bpm - c) for c in cuts))


if __name__ == "__main__":
    import sys
    SEEDS = [int(s) for s in (sys.argv[1].split(",") if len(sys.argv) > 1 else ["11", "12"])]
    OUT = sys.argv[2] if len(sys.argv) > 2 else "heldout_rows.json"
    os.makedirs("semi_heldout", exist_ok=True)
    t0 = time.time()
    rows = []
    for seed in SEEDS:
        for name, (segs, prof) in HELD.items():
            scs = {m: hl.BreathingScenario(segs, depth=d, phase_depth=d, seed=seed * 10 + i, name=name)
                   for i, (m, d) in enumerate(zip(MACS, DEPTHS))}
            path = f"semi_heldout/{name}_s{seed}.csv"
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
                    rows.append(dict(scenario=name, seed=seed, profile=prof, mac=mac, depth=scs[mac].depth,
                                     t=float(te), truth=float(truth[i]), truth_status=truth_status(scs[mac], te, prof),
                                     boundary_gap=nearest_boundary_gap(float(truth[i]), prof),
                                     new_bpm=float(T.bpm[i]), new_raw=float(T.bpm_raw[i]), new_reliable=bool(T.reliable[i]),
                                     new_status=T.status[i], new_motion=bool(T.motion[i]), new_pause=float(T.pause_s[i]),
                                     legacy_bpm=lb, legacy_plv=lplv, legacy_status=LEGACY_TO_STATUS.get(ltier, ltier)))
            print(f"{name} s{seed} {time.time() - t0:.0f}s", flush=True)
    # null: the raw format sample itself (no injected breathing)
    S = hl.load_csi_session(SRC)
    tracks = hl.analyze_session(S, hl.RRConfig(profile="adult"))
    leg = L.load_pjdsc_session(SRC)
    for mac in MACS:
        T = tracks[mac]
        for i, te in enumerate(T.t):
            lb, lplv, ltier = legacy_window(leg[mac], te)
            rows.append(dict(scenario="raw_sample_null", seed=0, profile="adult", mac=mac, depth=0.0, t=float(te),
                             truth=float("nan"), truth_status="absent", boundary_gap=float("nan"),
                             new_bpm=float(T.bpm[i]), new_raw=float(T.bpm_raw[i]), new_reliable=bool(T.reliable[i]),
                             new_status=T.status[i], new_motion=bool(T.motion[i]), new_pause=float(T.pause_s[i]),
                             legacy_bpm=lb, legacy_plv=lplv, legacy_status=LEGACY_TO_STATUS.get(ltier, ltier)))
    json.dump(rows, open(OUT, "w"))
    print("rows", len(rows), "time %.0fs" % (time.time() - t0))
