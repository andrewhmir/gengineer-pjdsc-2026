"""
hinigram_eval.py  (Hinigram v1.3.2)
==================================
Metrics for the semi-synthetic validation rows written by validate_heldout*.py.
Used by the notebook and the audit report so every number has one definition.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# held-out scenarios: name -> (segments [(t0, t1, breaths/min)], profile); 0 breaths/min = pause.
# Pauses sit where the real recording has no movement (about 30-60 s and 115-170 s).
SCENARIOS = {
    "adult_10": ([(0, 180, 10.0)], "adult"),
    "adult_17": ([(0, 180, 17.0)], "adult"),
    "adult_23": ([(0, 180, 23.0)], "adult"),
    "adult_32": ([(0, 180, 32.0)], "adult"),
    "pause_12s": ([(0, 140, 16.0), (140, 152, 0), (152, 180, 16.0)], "adult"),
    "pause_18s": ([(0, 40, 18.0), (40, 58, 0), (58, 180, 18.0)], "adult"),
    "infant_55": ([(0, 180, 55.0)], "infant_2_12m"),
    "child_34": ([(0, 180, 34.0)], "child_1_5y"),
    "short_8s": ([(0, 150, 16.0), (150, 158, 0), (158, 180, 16.0)], "adult"),
    "pause_14s": ([(0, 120, 17.0), (120, 134, 0), (134, 180, 17.0)], "adult"),
    "child_pause_25s": ([(0, 130, 30.0), (130, 155, 0), (155, 180, 30.0)], "child_1_5y"),
}
MACS = ["1a:00:00:00:00:01", "1a:00:00:00:00:02", "1a:00:00:00:00:03"]
DEPTHS = [0.05, 0.03, 0.015]          # breathing modulation on sensors 1, 2 and 3


def scenario(name: str, seed: int, mac: str):
    """The exact BreathingScenario used for one sensor of one held-out file."""
    import hinigram_live as hl
    segs, _ = SCENARIOS[name]
    i = MACS.index(mac)
    return hl.BreathingScenario(segs, depth=DEPTHS[i], phase_depth=DEPTHS[i], seed=seed * 10 + i, name=name)


def truth_curve(name: str, seed: int, mac: str, t_max: float = 173.2, step: float = 0.25):
    """(times, programmed breaths/min, pause spans) for plotting."""
    import hinigram_live as hl
    tt = np.arange(0, t_max, step)
    _, tb = hl.breathing_waveform(tt, scenario(name, seed, mac))
    return tt, tb, [(a, b) for a, b, r in SCENARIOS[name][0] if r == 0]


# programmed pause windows (start, end) in seconds, and whether the pause should be flagged
PAUSES = {
    "pause_12s": (140.0, 152.0, True),
    "pause_18s": (40.0, 58.0, True),
    "pause_14s": (120.0, 134.0, True),
    "child_pause_25s": (130.0, 155.0, True),
    "short_8s": (150.0, 158.0, False),     # negative control: shorter than the 10 s adult minimum
}
ORDER = ["typical", "watch", "urgent"]


def _pause_flag(df: pd.DataFrame) -> pd.Series:
    if "new_reason" in df:
        return (df.new_status == "urgent") & df.new_reason.fillna("").str.startswith("Possible breathing pause")
    return df.new_status == "urgent"


def bland_altman(est: pd.Series, truth: pd.Series, win_s: float = 30.0, hop_s: float = 2.0) -> dict:
    """Bias and 95% limits of agreement with approximate CIs (Bland & Altman 1986).

    Windows overlap (30 s windows every 2 s), so the CIs use an effective sample size of one
    window per 30 s instead of the raw count.
    """
    diff = (est - truth).dropna()
    n = len(diff)
    n_eff = max(2.0, n * hop_s / win_s)
    b, sd = float(diff.mean()), float(diff.std(ddof=1))
    se_b, se_l = sd / np.sqrt(n_eff), sd * np.sqrt(3.0 / n_eff)
    lo, hi = b - 1.96 * sd, b + 1.96 * sd
    return dict(n=n, n_eff=round(n_eff, 1), bias=b, sd=sd, loa=(lo, hi),
                bias_ci=(b - 1.96 * se_b, b + 1.96 * se_b),
                lower_ci=(lo - 1.96 * se_l, lo + 1.96 * se_l), upper_ci=(hi - 1.96 * se_l, hi + 1.96 * se_l))


def compute(rows) -> dict:
    d = pd.DataFrame(rows)
    out = {}
    # the raw format sample: no breathing reference, so the right answer is "cannot tell"
    n = d[d.scenario == "raw_sample_null"]
    out["null"] = dict(windows=len(n), v13_rates=int(n.new_reliable.sum()), v12_rates=int(np.isfinite(n.legacy_bpm).sum()),
                       v12_plv_median=float(n.legacy_plv.median()), v13_status=n.new_status.value_counts().to_dict(),
                       v12_status=n.legacy_status.value_counts().to_dict(), v13_urgent=int((n.new_status == "urgent").sum()))
    h = d[(d.scenario != "raw_sample_null") & np.isfinite(d.truth)].copy()
    h["e13"] = (h.new_bpm - h.truth).abs()
    h["e12"] = (h.legacy_bpm - h.truth).abs()
    rows_depth = []
    for dep, g in h.groupby("depth"):
        s = g[g.new_reliable]
        rows_depth.append(dict(depth=dep, windows=len(g),
                               v12_shown=np.isfinite(g.legacy_bpm).mean(), v13_shown=g.new_reliable.mean(),
                               v12_mae=g.e12.mean(), v13_mae=s.e13.mean() if len(s) else np.nan,
                               v12_within2=(g.e12 <= 2).mean(), v13_within2=(s.e13 <= 2).mean() if len(s) else np.nan,
                               v13_n=len(s)))
    out["per_depth"] = pd.DataFrame(rows_depth)
    rows_prof = []
    for prof, g in h[h.depth >= 0.03].groupby("profile"):
        s = g[g.new_reliable]
        rows_prof.append(dict(profile=prof, windows=len(g), v13_shown=g.new_reliable.mean(),
                              v13_mae=s.e13.mean() if len(s) else np.nan, v13_within2=(s.e13 <= 2).mean() if len(s) else np.nan,
                              v12_mae=g.e12.mean(), v12_within2=(g.e12 <= 2).mean()))
    out["per_profile"] = pd.DataFrame(rows_prof)
    g3 = h[h.new_reliable & (h.depth >= 0.03)]
    out["ba"] = bland_altman(g3.new_bpm, g3.truth)
    big = g3[(g3.new_bpm - g3.truth).abs() > 5]
    out["big_errors"] = big[["scenario", "seed", "mac", "depth", "t", "truth", "new_bpm", "new_status"]].reset_index(drop=True)
    clean = g3[(g3.new_bpm - g3.truth).abs() <= 5]
    out["ba_without_big"] = bland_altman(clean.new_bpm, clean.truth)
    # status agreement where the true status is unambiguous
    x = d[d.truth_status.isin(ORDER)]
    conf = {}
    for col, name in (("legacy_status", "v1.2"), ("new_status", "v1.3")):
        conf[name] = pd.crosstab(x.truth_status, x[col], normalize="index").reindex(ORDER)
    out["confusion"] = conf
    urg = x[x.truth_status == "urgent"]
    out["true_urgent"] = dict(windows=len(urg), v12_no_concern=float((urg.legacy_status == "typical").mean()),
                              v13_no_concern=float((urg.new_status == "typical").mean()),
                              v13_urgent=float((urg.new_status == "urgent").mean()),
                              v13_abstained=float(urg.new_status.isin(["no_reading", "moving"]).mean()))
    # false reassurance: a programmed pause has lasted at least the minimum, yet a rate-based state is shown
    pz = d[d.scenario.isin(list(PAUSES)) & (d.truth_status == "urgent")]
    rate_based = pz.new_status.isin(["typical", "watch"]) | ((pz.new_status == "urgent") & ~_pause_flag(pz))
    out["pause_reassurance"] = dict(windows=len(pz), rate_state=float(rate_based.mean()) if len(pz) else np.nan,
                                    no_concern=float((pz.new_status == "typical").mean()) if len(pz) else np.nan,
                                    n_no_concern=int((pz.new_status == "typical").sum()))
    ans = x[x.new_status.isin(ORDER)]
    out["answered_accuracy"] = dict(windows=len(ans), accuracy=float((ans.new_status == ans.truth_status).mean()))
    # pauses: detection and timing per run (seed x sensor), plus false pause flags elsewhere
    pr = []
    d["pause_flag"] = _pause_flag(d)
    for name, (a, b, should) in PAUSES.items():
        for (seed, mac, dep), g in d[d.scenario == name].groupby(["seed", "mac", "depth"]):
            g = g.sort_values("t")
            hit = g[(g.t >= a) & (g.t <= b + 30) & g.pause_flag]
            before = g[(g.t < a) & g.pause_flag]
            pr.append(dict(scenario=name, seed=int(seed), mac=mac[-2:], depth=float(dep), pause_s=b - a, should_flag=should,
                           flagged=bool(len(hit)), latency_s=float(hit.t.iloc[0] - a) if len(hit) else np.nan,
                           flagged_before_pause=int(len(before)),
                           clears_after_s=float(g[(g.t > b) & ~g.pause_flag & (g.t > (hit.t.iloc[0] if len(hit) else b))].t.iloc[0] - b)
                           if len(hit) and len(g[(g.t > b) & ~g.pause_flag & (g.t > hit.t.iloc[0])]) else np.nan))
    out["pauses"] = pd.DataFrame(pr)
    nop = d[~d.scenario.isin(list(PAUSES) + ["raw_sample_null"])]
    # needs the reason text to tell a pause flag from a rate-based "needs help now"
    out["false_pause"] = dict(windows=len(nop), flags=int(nop.pause_flag.sum())) if "new_reason" in d else None
    return out


def pause_summary(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (name, dep), g in p.groupby(["scenario", "depth"]):
        rows.append(dict(scenario=name, depth=dep, runs=len(g), should_flag=bool(g.should_flag.iloc[0]),
                         flagged=int(g.flagged.sum()),
                         latency_s=("-" if not g.flagged.any() else
                                    f"{g.latency_s.min():.0f} to {g.latency_s.max():.0f}" if g.latency_s.nunique() > 1 else f"{g.latency_s.min():.0f}")))
    return pd.DataFrame(rows)
