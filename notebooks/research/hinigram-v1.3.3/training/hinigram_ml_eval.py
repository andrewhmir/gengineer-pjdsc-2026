"""
hinigram_ml_eval.py  (Hinigram v1.3.2, evaluation of the learned estimators)
===========================================================================
Scores every trained arm and the frozen v1.3.2 DSP on held-out set 5 with the same windows and the same
screening state machine, then runs paired, Holm-corrected contrasts in the style of the team's ResoNet paper.

A model arm replaces only the DSP's rate and its "reliable" flag; the movement flag, the pause detector, the
recency signals and the persistence rules all stay the DSP's, so a change in screening comes from the
estimator alone.
"""
from __future__ import annotations

import glob
import json
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy import stats

import hinigram_dataset as hd
import hinigram_live as hl

RUNS = os.path.join(hd.HERE, "mlruns")
ARM_ORDER = ["dsp", "shallow", "lin_power", "lin_sync", "lin_surrogate", "nl_power", "nl_sync", "nl_surrogate"]
ARM_NAME = {"dsp": "DSP v1.3.2 (rules)", "shallow": "ShallowNet (learned band power)", "lin_power": "ResoNet linear, power readout",
            "lin_sync": "ResoNet linear, sync readout", "lin_surrogate": "ResoNet linear, surrogate readout",
            "nl_power": "ResoNet nonlinear, power readout", "nl_sync": "ResoNet nonlinear, sync readout",
            "nl_surrogate": "ResoNet nonlinear, surrogate readout"}


def load_test(kind="test5"):
    files = sorted(glob.glob(os.path.join(hd.HERE, "mldata", kind, "*.npz")))
    return [hd.load_npz(f) | {"path": f} for f in files]


def runs_available():
    out = {}
    for f in sorted(glob.glob(os.path.join(RUNS, "*_summary.json"))):
        j = json.load(open(f))
        out.setdefault(j["arm"], {}).setdefault(j["seed"], {})[j["fold"]] = j
    return out


def model_predictions(arm, seed, test, kind="test"):
    """Per (file, link): rate, sd, p_present and the calibrated 'shows a rate' flag, from the three folds."""
    pred = {}
    for fold in range(3):
        tag = f"{arm}_f{fold}_s{seed}"
        z = np.load(os.path.join(RUNS, tag + "_pred.npz"))
        cal = json.load(open(os.path.join(RUNS, tag + "_summary.json")))["calibration"]
        fi, li, k = z[f"{kind}_file"], z[f"{kind}_link"], z[f"{kind}_k"]
        for f in np.unique(fi):
            m = fi == f
            order = np.argsort(k[m])
            r, sd, pp = z[f"{kind}_rate"][m][order], z[f"{kind}_sd"][m][order], z[f"{kind}_p_present"][m][order]
            tau = cal["tau"] if cal["val_coverage"] > 0 else -np.inf     # no validation threshold reached 95%: show nothing
            pred[(int(f), int(li[m][0]))] = dict(rate=r, sd=sd, p=pp, shown=(pp > 0.5) & (sd <= tau), tau=tau)
    return pred


def screening(L, bpm, reliable):
    d = L["dsp"]
    trk = SimpleNamespace(t=L["t"][L["ends"] - 1].astype(float), bpm=np.where(reliable, bpm, np.nan), reliable=reliable.astype(bool),
                          motion=d["motion"].astype(bool), pause_s=d["pause_s"], base_period=d["period"], resp_rms_ratio=d["quiet"],
                          pause_snr=d["snr"], recent_low=d["recent_low"].astype(bool), recent_gated=d["recent_gated"].astype(bool),
                          pause_est=np.array([]))
    status, reason = hl.screening_flags(trk, hl.RRConfig(profile=L["profile"]))
    return np.array(status), np.array(reason)


def window_table(test, arms_seeds):
    """One row per (arm, seed, file, link, window) with truth, shown rate and screening state."""
    rows = []
    for arm, seed, pred in arms_seeds:
        for fi, d in enumerate(test):
            spec = d["spec"]
            for li, L in enumerate(d["links"]):
                if arm == "dsp":
                    bpm, shown, sd = L["dsp"]["bpm"], L["dsp"]["reliable"].astype(bool), 1.0 - L["dsp"]["quality"]
                    raw = L["dsp"]["raw"]
                    status, reason = L["dsp"]["status"], L["dsp"]["reason"]
                else:
                    pr = pred[(fi, li)]
                    bpm, shown, raw = pr["rate"], pr["shown"], pr["rate"]
                    sd = np.where(pr["p"] > 0.5, pr["sd"], pr["sd"] + 100.0)     # "breathing absent" ranks last
                    status, reason = screening(L, bpm, shown)
                rows.append(pd.DataFrame(dict(
                    arm=arm, seed=seed, file=fi, link=li, scenario=spec.get("scenario", spec["name"]), rot=spec.get("rot", -1),
                    depth=spec["links"][li]["depth"], profile=L["profile"], k=np.arange(len(L["ends"])), t=L["t"][L["ends"] - 1],
                    truth=L["rate"], present=L["present"], truth_status=L["truth_status"], est=np.where(shown, bpm, np.nan), est_raw=raw, shown=shown, score=sd,
                    status=status, reason=reason, motion=L["dsp"]["motion"].astype(bool))))
    return pd.concat(rows, ignore_index=True)


def rate_metrics(w):
    d = w[np.isfinite(w.truth)]
    s = d[d.shown]
    err = (s.est - s.truth).abs()
    return dict(windows=len(d), shown=len(s) / max(len(d), 1), within2=float((err <= 2).mean()) if len(s) else np.nan,
                mae=float(err.mean()) if len(s) else np.nan, off5=float((err > 5).mean()) if len(s) else np.nan,
                useful=float(((d.shown) & ((d.est - d.truth).abs() <= 2)).mean()))


def screening_metrics(w):
    import hinigram_eval as he
    x = w[w.truth_status.isin(["typical", "watch", "urgent"])]
    pause_flag = (x.status == "urgent") & x.reason.astype(str).str.startswith("Possible breathing pause")
    urg = x[x.truth_status == "urgent"]
    ans = x[x.status.isin(["typical", "watch", "urgent"])]
    pz = w[w.scenario.isin(list(he.PAUSES)) & (w.truth_status == "urgent")]
    return dict(answered=len(ans) / max(len(x), 1), answered_correct=float((ans.status == ans.truth_status).mean()) if len(ans) else np.nan,
                urgent_no_concern=float((urg.status == "typical").mean()) if len(urg) else np.nan,
                urgent_flagged=float((urg.status == "urgent").mean()) if len(urg) else np.nan,
                pause_no_concern=int((pz.status == "typical").sum()), pause_windows=len(pz),
                false_watch_or_urgent=float(x[x.truth_status == "typical"].status.isin(["watch", "urgent"]).mean()))


def risk_coverage(w, grid=np.linspace(0.05, 1.0, 20)):
    """Within +/-2 accuracy against coverage when windows are ranked by each method's own confidence score."""
    d = w[np.isfinite(w.truth) & np.isfinite(w.est_raw)].sort_values("score", kind="stable")
    ok = ((d.est_raw - d.truth).abs() <= 2).to_numpy()
    n_def = int(np.isfinite(w.truth).sum())
    out = []
    for c in grid:
        n = int(round(c * n_def))
        if n < 10 or n > len(d):
            out.append(np.nan)
            continue
        out.append(float(ok[:n].mean()))
    return np.array(out)


def per_run(w, metric="useful"):
    """Per (file, link) value of a metric, averaged over training seeds, for paired tests."""
    g = []
    for (arm, f, l), d in w.groupby(["arm", "file", "link"]):
        vals = [rate_metrics(dd)[metric] for _, dd in d.groupby("seed")]
        g.append(dict(arm=arm, file=f, link=l, value=float(np.nanmean(vals)) if len(vals) else np.nan))
    return pd.DataFrame(g).pivot_table(index=["file", "link"], columns="arm", values="value")


def paired(table, a, b):
    d = (table[a] - table[b]).dropna()
    n = len(d)
    if n < 3 or np.allclose(d, 0):
        return dict(contrast=f"{a} - {b}", n=n, mean=float(d.mean()) if n else np.nan, ci=(np.nan, np.nan), dz=np.nan, t_p=np.nan, w_p=np.nan, wins=np.nan)
    se = d.std(ddof=1) / np.sqrt(n)
    tcrit = stats.t.ppf(0.975, n - 1)
    w = stats.wilcoxon(d, zero_method="wilcox")
    return dict(contrast=f"{a} - {b}", n=n, mean=float(d.mean()), ci=(float(d.mean() - tcrit * se), float(d.mean() + tcrit * se)),
                dz=float(d.mean() / d.std(ddof=1)) if d.std(ddof=1) > 0 else np.nan, t_p=float(stats.ttest_rel(table[a][d.index], table[b][d.index]).pvalue),
                w_p=float(w.pvalue), wins=f"{int((d > 0).sum())}/{int((d != 0).sum())}")


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    m = len(p)
    running = 0.0
    for r, i in enumerate(order):
        running = max(running, (m - r) * p[i])
        adj[i] = min(1.0, running)
    return adj
