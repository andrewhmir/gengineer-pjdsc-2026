"""
hinigram_paced.py  (Hinigram v1.3.2, scoring the paced-breathing accuracy check)
================================================================================
Hinigram runs on CSI alone. To check its accuracy without a respiration belt, a person sits on one chair and breathes
with the board's pacer at known rates (the "Check accuracy with paced breathing" panel). The board scores the chair live
when the receiver is connected, and saves a pacer log (JSON) with the wall-clock start of the check and its steps.

Offline: record a CSV from the receiver while the pacer runs, then
    python hinigram_paced.py <recording.csv> <pacer_log.json> [age profile]
Only 30 s windows that lie wholly inside a step are scored, exactly as the board does.

make_rehearsal() builds an example: the real format sample with breathing that follows the short plan on one sensor,
plus the matching pacer log, so the scoring can be tried before any recording.
"""
from __future__ import annotations

import datetime
import json
import os
import sys

import numpy as np
import pandas as pd

import hinigram_live as hl

HERE = os.path.dirname(os.path.abspath(__file__))
PLANS = {"standard": dict(rates=[8, 12, 16, 20, 24], step=90, rest=30), "short": dict(rates=[10, 16, 22], step=50, rest=10)}
SEATS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def plan_steps(name: str) -> list:
    p, out, t = PLANS[name], [], 0
    for k, r in enumerate(p["rates"]):
        out.append(dict(rate=r, start_s=t, end_s=t + p["step"])); t += p["step"]
        if k < len(p["rates"]) - 1:
            out.append(dict(rest=True, start_s=t, end_s=t + p["rest"])); t += p["rest"]
    return out


def score(csv_path: str, log_path: str, profile: str = "adult"):
    """Per-step table: windows scored, readings shown, readings within +/-2/min, median reading, mean absolute error."""
    log = json.load(open(log_path, encoding="utf-8"))
    if log.get("kind") != "hinigram-paced-check":
        raise ValueError("not a Hinigram pacer log")
    S = hl.load_csi_session(csv_path)
    macs = list(S.macs)
    mac = log.get("mac") if log.get("mac") in S.links else macs[SEATS.index(log["seat"])]
    cfg = hl.RRConfig(profile=profile)
    t_end = min(float(L.t[-1]) for L in S.links.values())
    T = hl.track_link(hl.link_features(S.links[mac], fs=cfg.fs, t_end=t_end), cfg)
    t0 = datetime.datetime.fromisoformat(log["startedAt"].replace("Z", "+00:00")).timestamp() - S.t0_host
    t, bpm, rel = np.asarray(T.t, float), np.asarray(T.bpm, float), np.asarray(T.reliable, bool)
    rows = []
    for st in log["steps"]:
        if st.get("rest"):
            continue
        m = (t >= t0 + st["start_s"] + 32) & (t <= t0 + st["end_s"])
        ok = m & rel & np.isfinite(bpm)
        err = np.abs(bpm[ok] - st["rate"])
        rows.append(dict(paced_rate=st["rate"], windows=int(m.sum()), shown=int(ok.sum()), within2=int((err <= 2).sum()),
                         median_reading=round(float(np.median(bpm[ok])), 1) if ok.any() else np.nan,
                         mean_abs_error=round(float(err.mean()), 2) if ok.any() else np.nan))
    return pd.DataFrame(rows), mac


def make_rehearsal(out_dir: str, plan: str = "short", offset_s: float = 2.0, depth: float = 0.05):
    """The real format sample with breathing that follows `plan` on its first sensor, and the matching pacer log."""
    src = os.path.join(HERE, "demo_20261019_024431.csv")
    S = hl.load_csi_session(src)
    macs = list(S.macs)
    steps = plan_steps(plan)
    segs, prev = [(0.0, offset_s, 14.0)], offset_s
    for st in steps:
        segs.append((offset_s + st["start_s"], offset_s + st["end_s"], 14.0 if st.get("rest") else float(st["rate"])))
    segs.append((offset_s + steps[-1]["end_s"], 400.0, 14.0))
    scen = {macs[0]: hl.BreathingScenario(segs, depth=depth, phase_depth=depth, seed=501, name="paced_" + plan)}
    for i, m in enumerate(macs[1:]):
        scen[m] = hl.BreathingScenario([(0.0, 400.0, 15.0 + 2 * i)], depth=depth, phase_depth=depth, seed=502 + i, name="steady")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "paced_rehearsal.csv")
    hl.inject_breathing(src, csv_path, scen)
    started = datetime.datetime.fromtimestamp(S.t0_host + offset_s, datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    log = dict(kind="hinigram-paced-check", version=1, seat="A", mac=macs[0], plan=plan, startedAt=started, complete=True, steps=steps,
               liveStart_t=None, source="file", note="Rehearsal: breathing injected to follow the pacer on the first sensor of the real format sample.")
    log_path = os.path.join(out_dir, "paced_rehearsal_log.json")
    json.dump(log, open(log_path, "w", encoding="utf-8"), indent=1)
    return csv_path, log_path


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        tab, mac = score(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "adult")
    else:
        c, l = make_rehearsal(os.path.join(HERE, "paced_check"))
        print("rehearsal written:", c, l)
        tab, mac = score(c, l)
    print("sensor", mac)
    print(tab.to_string(index=False))
    n, s, w = tab.windows.sum(), tab.shown.sum(), tab.within2.sum()
    print(f"overall: {w} of {s} readings within +/-2/min ({100 * w / max(s, 1):.0f}%), a rate shown in {100 * s / max(n, 1):.0f}% of {n} windows")
