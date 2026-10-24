"""
hinigram_ml_report.py  (Hinigram v1.3.2, tables and figures for the learned estimators)
=====================================================================================
Used by the training notebook. Everything is computed from the cached data in mldata/ and the saved
predictions in mlruns/; nothing is retrained here.
"""
from __future__ import annotations

import glob
import json
import os
import pickle

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import hinigram_style as hs
import hinigram_dataset as hd
import hinigram_ml_eval as me

STYLE = {
    "dsp":           dict(color=hs.INK, ls="-", marker="o", name="DSP v1.3.2 (rules)"),
    "shallow":       dict(color="#D55E00", ls="-", marker="s", name="ShallowNet (learned band power)"),
    "shallow-p0":    dict(color="#D55E00", ls=(0, (4, 3)), marker="X", name="ShallowNet, no pooling"),
    "lin_power":     dict(color="#009E73", ls="-", marker="D", name="ResoNet, power readout"),
    "lin_power-p0":  dict(color="#009E73", ls=(0, (4, 3)), marker="d", name="ResoNet, power readout, no pooling"),
    "lin_surrogate": dict(color="#CC79A7", ls="-", marker="v", name="ResoNet, shift surrogate (paper's control)"),
    "lin_randphase": dict(color="#E69F00", ls="-", marker="P", name="ResoNet, random-phase surrogate"),
    "lin_sync":      dict(color="#0072B2", ls="-", marker="^", name="ResoNet, sync readout"),
}


def name(arm):
    return STYLE.get(arm, {}).get("name", arm)


def trained_arms(seed=0):
    have = {}
    for f in glob.glob(os.path.join(me.RUNS, f"*_s{seed}_summary.json")):
        j = json.load(open(f))
        have.setdefault(j["arm"], set()).add(j["fold"])
    return [a for a in STYLE if a != "dsp" and have.get(a) == {0, 1, 2}]


def collect(seed=0, arms=None):
    test = me.load_test("test5")
    arms = trained_arms(seed) if arms is None else arms
    spec = [("dsp", seed, None)] + [(a, seed, me.model_predictions(a, seed, test)) for a in arms]
    return test, me.window_table(test, spec), arms


def null_test(arms, seed=0):
    raw = me.load_test("raw")[0]
    rows = [dict(method=name("dsp"), windows=sum(len(L["ends"]) for L in raw["links"]),
                 shown=int(sum(L["dsp"]["reliable"].sum() for L in raw["links"])))]
    for a in arms:
        n = s = 0
        for fold in range(3):
            z = np.load(os.path.join(me.RUNS, f"{a}_f{fold}_s{seed}_pred.npz"))
            cal = json.load(open(os.path.join(me.RUNS, f"{a}_f{fold}_s{seed}_summary.json")))["calibration"]
            tau = cal["tau"] if cal["val_coverage"] > 0 else -np.inf
            shown = (z["raw_p_present"] > 0.5) & (z["raw_sd"] <= tau)
            n += len(shown); s += int(shown.sum())
        rows.append(dict(method=name(a), windows=n, shown=s))
    return pd.DataFrame(rows)


def rate_table(w, arms):
    out = []
    for a in ["dsp"] + arms:
        d = w[w.arm == a]
        r = me.rate_metrics(d)
        row = dict(method=name(a), shown=r["shown"], within2=r["within2"], mae=r["mae"], off5=r["off5"], useful=r["useful"])
        for dep in sorted(d.depth.unique(), reverse=True):
            rr = me.rate_metrics(d[d.depth == dep])
            row[f"shown {dep * 100:.1f}%"] = rr["shown"]
            row[f"within2 {dep * 100:.1f}%"] = rr["within2"]
        out.append(row)
    return pd.DataFrame(out)


def fold_table(w, arms, metric="useful"):
    """Each fold is a separately trained model tested on its held-out sensor: does the ranking hold in all three?"""
    rows = []
    for a in ["dsp"] + arms:
        d = w[w.arm == a]
        rows.append(dict(method=name(a), **{f"sensor {l + 1}": me.rate_metrics(d[d.link == l])[metric] for l in range(3)}))
    return pd.DataFrame(rows)


def screening_table(w, arms):
    return pd.DataFrame([dict(method=name(a), **me.screening_metrics(w[w.arm == a])) for a in ["dsp"] + arms])


def contrasts(w, pairs, metric="useful"):
    tab = me.per_run(w, metric)
    res = [me.paired(tab, a, b) for a, b in pairs if a in tab and b in tab]
    adj = me.holm([r["w_p"] for r in res])
    for r, p in zip(res, adj):
        r["holm_p"] = float(p)
    return pd.DataFrame(res), tab


def best_variant(base, seed=0):
    """Pooled or not: pick the variant with the higher mean validation coverage (validation only, never the test set)."""
    best, score = None, -1.0
    for a in (base, base + "-p0"):
        try:
            cov = [json.load(open(os.path.join(me.RUNS, f"{a}_f{f}_s{seed}_summary.json")))["calibration"]["val_coverage"] for f in range(3)]
        except FileNotFoundError:
            continue
        if np.mean(cov) > score:
            best, score = a, float(np.mean(cov))
    return best


SHORT = {"lin_sync": "sync", "lin_randphase": "random-phase surrogate", "lin_power": "power", "lin_power-p0": "power without pooling",
         "lin_surrogate": "shift surrogate", "shallow": "ShallowNet", "shallow-p0": "ShallowNet without pooling", "dsp": "DSP"}
WHY = {("lin_sync", "lin_randphase"): " (phase angle)", ("lin_sync", "lin_power"): " (readout swap)",
       ("lin_sync", "lin_power-p0"): " (best power variant)", ("lin_sync", "lin_surrogate"): " (paper's control)"}


def contrast_label(a, b):
    ra = ("ResoNet " if a.startswith("lin_") and not b.startswith("lin_") else "") + SHORT.get(a, a)
    return f"{ra} - {SHORT.get(b, b)}{WHY.get((a, b), '')}"


def main_pairs(seed=0):
    """The contrasts reported, fixed before looking at the test set except for the validation-chosen variants."""
    P, S = best_variant("lin_power", seed), best_variant("shallow", seed)
    pairs = [("lin_sync", "lin_randphase"), ("lin_sync", "lin_power")]
    if P and P != "lin_power":
        pairs.append(("lin_sync", P))
    pairs += [("lin_sync", "lin_surrogate"), ("lin_sync", S), ("lin_sync", "dsp"), (S, "dsp")]
    return [p for p in pairs if p[0] and p[1]]


def seed_tables(seeds=(0, 1), metric="useful"):
    """Replication: the same arms trained again from a different seed, scored on the same test windows."""
    rows, cons = [], []
    seeds = [s for s in seeds if trained_arms(s)]
    common = set.intersection(*[set(trained_arms(s)) for s in seeds]) | {"dsp"} if seeds else set()
    pairs = [p for p in main_pairs(0) if p[0] in common and p[1] in common]     # the same family of contrasts for every seed
    for s in seeds:
        _, w, arms = collect(seed=s, arms=trained_arms(s))
        for a in ["dsp"] + arms:
            r = me.rate_metrics(w[w.arm == a])
            q = me.screening_metrics(w[w.arm == a])
            rows.append(dict(seed=s, arm=a, method=name(a), shown=r["shown"], within2=r["within2"], off5=r["off5"], useful=r["useful"],
                             answered=q["answered"], answered_correct=q["answered_correct"], urgent_no_concern=q["urgent_no_concern"],
                             pause_no_concern=q["pause_no_concern"], pause_windows=q["pause_windows"]))
        if pairs:
            res, _ = contrasts(w, pairs, metric)
            res.insert(0, "seed", s)
            cons.append(res)
    return pd.DataFrame(rows), (pd.concat(cons, ignore_index=True) if cons else pd.DataFrame())


# --------------------------------------------------------------------------- figures
def fig_preprocessing(path=None, link=1, k=40):
    """One window through the preprocessing: the cleaned CSI channels, the per-window PCA, what the model sees."""
    if path is None:                      # a clear example: 3.5 to 6% modulation, breathing throughout, no movement
        for cand in sorted(glob.glob(os.path.join(hd.HERE, "mldata", "val", "*.npz"))):
            dd = hd.load_npz(cand)
            hit = [(li, kk) for li, LL in enumerate(dd["links"]) if 0.035 <= dd["spec"]["links"][li]["depth"] <= 0.06
                   for kk in range(20, len(LL["ends"]) - 5) if np.isfinite(LL["rate"][kk]) and not LL["dsp"]["motion"][kk]
                   and LL["activity"][LL["ends"][kk] - hd.NW:LL["ends"][kk]].max() < 1.0]
            if hit:
                path, (link, k) = cand, hit[len(hit) // 2]
                break
    d = hd.load_npz(path)
    L = d["links"][link]
    e = int(L["ends"][k])
    raw = L["X"][e - hd.NW:e]
    Wd = hd.window_inputs(L["X"], np.array([e]))
    P = hd.pca_components(Wd, np.array([hd.PROFILES.index(str(L["profile"]))]))[0]
    rate = float(L["rate"][k]); dep = d["spec"]["links"][link]["depth"]
    fig = plt.figure(figsize=(11.5, 6.4))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.25, 1.25, 1], height_ratios=[1, 1], hspace=0.55, wspace=0.32)
    t10 = np.arange(hd.NW) / hd.FS
    ax = fig.add_subplot(gs[:, 0])
    Z = (raw - raw.mean(0)) / (raw.std(0) + 1e-9)
    ax.imshow(Z.T, aspect="auto", cmap="hinigram_div", vmin=-3, vmax=3, extent=[0, 30, Z.shape[1], 0], interpolation="nearest")
    ax.axhline(51, color=hs.INK, lw=1)
    ax.set_yticks([25, 76]); ax.set_yticklabels(["amplitude\nshape", "phase"])
    ax.set_xlabel("Seconds in the window"); ax.grid(False)
    ax.set_title("A  Cleaned CSI: 51 subcarriers × 2, 10 Hz")
    t5 = np.arange(hd.T_WIN) * hd.DT
    ax = fig.add_subplot(gs[0, 1])
    for j in range(P.shape[1]):
        ax.plot(t5, P[:, j] - 3.2 * j, color=hs.TRACE if j == 0 else hs.INK_3, lw=1.6 if j == 0 else 1.1)
    ax.set_yticks([-3.2 * j for j in range(P.shape[1])]); ax.set_yticklabels([f"PC{j + 1}" for j in range(P.shape[1])])
    ax.set_xlabel("Seconds"); ax.set_title("B  Model input: top 4 components, 5 Hz")
    ax = fig.add_subplot(gs[1, 1])
    f = np.fft.rfftfreq(2048, hd.DT) * 60
    for j in range(P.shape[1]):
        S = np.abs(np.fft.rfft(P[:, j] * np.hanning(len(P)), 2048)) ** 2
        ax.plot(f, S / S.max() - 1.15 * j, color=hs.TRACE if j == 0 else hs.INK_3, lw=1.4 if j == 0 else 1.0)
    ax.axvline(rate, **hs.REF_STYLE)
    ax.set_xlim(0, 90); ax.set_yticks([]); ax.set_xlabel("Breaths per minute")
    ax.set_title(f"C  Spectra; dashed = true rate {rate:.1f}/min")
    ax = fig.add_subplot(gs[:, 2]); ax.axis("off")
    steps = [("Parse and split", "CSI_DATA lines, one stream per sensor MAC"),
             ("Receiver clock", "unwrapped local_timestamp, loss measured"),
             ("Clean each packet", "divide by its RMS (gain steps), remove phase slope"),
             ("Resample", "10 Hz grid, Hampel filter for spikes"),
             ("Window", "30 s ending at the DSP's hop times"),
             ("Normalise", "average to 5 Hz, detrend, z-score each channel"),
             ("Band-pass and PCA", "age-profile band inside the window, top 4 components"),
             ("Labels", "mean true rate; breathing in the newest 6 s; true state")]
    y = 0.98
    for a, b in steps:
        ax.text(0.0, y, a, fontsize=10, fontweight="bold", color=hs.INK, va="top", transform=ax.transAxes)
        ax.text(0.0, y - 0.045, b, fontsize=8.8, color=hs.INK_2, va="top", transform=ax.transAxes)
        y -= 0.122
    hs.suptitle(fig, "Preprocessing: from packets to model input",
                f"A validation window ({d['spec']['links'][link]['profile'].replace('_', ' ')}, {dep * 100:.1f}% modulation). Only samples inside the window are used.", y=1.02)
    return fig


def fig_training(arms, fold=0, seed=0):
    fig, ax = plt.subplots(figsize=(8.6, 3.8))
    for a in arms:
        j = json.load(open(os.path.join(me.RUNS, f"{a}_f{fold}_s{seed}_summary.json")))
        h = pd.DataFrame(j["hist"])
        st = STYLE[a]
        ax.plot(h.epoch, h.val, color=st["color"], ls=st["ls"], lw=1.8, label=st["name"])
        b = h.val.idxmin()
        ax.plot(h.epoch[b], h.val[b], marker=st["marker"], color=st["color"], ms=7, ls="none")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Validation loss (NLL + BCE)")
    ax.set_title(f"Validation loss while training (fold {fold + 1}: trained on the other two sensors)")
    ax.legend(loc="upper right", ncol=1)
    return fig


def fig_oscillators(arm="lin_sync", seed=0):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    f0 = np.exp(np.linspace(np.log(0.10), np.log(1.40), hd.N_OSC)) * 60
    for fold in range(3):
        P = pickle.load(open(os.path.join(me.RUNS, f"{arm}_f{fold}_s{seed}_params.pkl"), "rb"))["params"]
        f = np.asarray(P["w"]) / (2 * np.pi) * 60
        mu = -(np.log1p(np.exp(np.asarray(P["a_mu"]))) + 0.02)
        o = np.argsort(f0)
        axes[0].plot(f0[o], f[o], marker="os^"[fold], ls="none", color=hs.SENSOR[fold + 1], ms=6, label=f"fold {fold + 1}")
        axes[1].plot(f[o], -mu[o] / (2 * np.pi) * 60, marker="os^"[fold], ls="none", color=hs.SENSOR[fold + 1], ms=6, label=f"fold {fold + 1}")
    axes[0].plot([5, 90], [5, 90], **hs.REF_STYLE)
    axes[0].set_xscale("log"); axes[0].set_yscale("log")
    axes[0].set_xlabel("Starting frequency (/min)"); axes[0].set_ylabel("Learned frequency (/min)")
    axes[0].set_title("A  Oscillator frequencies after training")
    axes[1].axhline(0.33 / (2 * np.pi) * 60 + 0.02 / (2 * np.pi) * 60, **hs.REF_STYLE)
    axes[1].set_xscale("log")
    from matplotlib.ticker import FixedLocator, NullLocator, ScalarFormatter
    for ax, which in ((axes[0], "xy"), (axes[1], "x")):
        for k in which:
            axis = ax.xaxis if k == "x" else ax.yaxis
            axis.set_major_locator(FixedLocator([5, 10, 20, 40, 80]))
            axis.set_minor_locator(NullLocator())
            axis.set_major_formatter(ScalarFormatter())
    axes[1].set_xlabel("Learned frequency (/min)"); axes[1].set_ylabel("Half-bandwidth (/min)")
    axes[1].set_title("B  Damping: every oscillator stays a damped resonator")
    axes[0].legend(loc="upper left")
    hs.suptitle(fig, f"What the {name(arm)} learned", "Dashed: starting values. Linear bank, so damping is negative by construction.", y=1.05)
    fig.tight_layout()
    return fig


def fig_risk_coverage(w, arms, grid=np.linspace(0.05, 0.8, 16)):
    fig, ax = plt.subplots(figsize=(10.4, 4.6))
    for a in ["dsp"] + arms:
        st = STYLE[a]
        acc = me.risk_coverage(w[w.arm == a], grid)
        ax.plot(grid * 100, acc * 100, color=st["color"], ls=st["ls"], lw=2, label=st["name"])
        r = me.rate_metrics(w[w.arm == a])
        ax.plot(r["shown"] * 100, r["within2"] * 100, marker=st["marker"], color=st["color"], ms=9, ls="none", mec=hs.PAPER, mew=1.2)
    ax.set_xlabel("Windows given a rate (%), most confident first")
    ax.set_ylabel("Of those, within ±2/min (%)")
    ax.set_ylim(20, 101); ax.set_xlim(0, grid[-1] * 100 + 2)
    ax.set_title("Accuracy against coverage on held-out set 5")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False,
              title="Markers: each method's\nown operating point", title_fontsize=9, alignment="left")
    fig.tight_layout()
    return fig


def surrogate_leak_demo(rates=(10, 20, 30, 45), seed=0):
    """Why a fixed circular shift is not a phase-destroying control for breathing.

    A clean breathing-like input drives two linear oscillators. For each rate, the coherence C between them is
    computed as is, after the paper's fixed per-oscillator circular shifts, and after random phase rotations.
    The shift keeps |C| and moves the angle by -2 pi f (s_1 - s_2), so the angle still tracks the rate."""
    T, dt, skip = hd.T_WIN, hd.DT, hd.SKIP
    t = np.arange(T) * dt
    lam = np.array([-0.35 + 2j * np.pi * 0.25, -0.35 + 2j * np.pi * 0.45])
    h = np.exp(lam[None, :] * t[:, None]) * dt
    s = hd.surrogate_shifts(seed)[:2]
    rng = np.random.default_rng(seed)
    rows = []
    for r in rates:
        x = np.sin(2 * np.pi * r / 60 * t) + 0.25 * np.sin(4 * np.pi * r / 60 * t + 0.6)
        z = np.stack([np.convolve(x, h[:, j])[:T] for j in range(2)], 1)[skip:]
        u = z / np.abs(z)
        C = np.mean(u[:, 0] * np.conj(u[:, 1]))
        n = len(u)
        us = np.stack([np.roll(u[:, j], s[j]) for j in range(2)], 1)
        Cs = np.mean(us[:, 0] * np.conj(us[:, 1]))
        th = rng.uniform(0, 2 * np.pi, (200, 2))
        Cr = np.mean(u[:, 0] * np.conj(u[:, 1])) * np.exp(1j * (th[:, 0] - th[:, 1]))
        rows.append({"rate (/min)": r, "|C| as is": abs(C), "angle as is (deg)": np.degrees(np.angle(C)),
                     "|C| fixed shift": abs(Cs), "angle fixed shift (deg)": np.degrees(np.angle(Cs)),
                     "|C| random phase": float(np.mean(np.abs(Cr))), "angle random phase": "uniform"})
    return pd.DataFrame(rows).round(2)


def fig_contrasts(res, labels=None):
    fig, ax = plt.subplots(figsize=(8.6, 0.55 * len(res) + 1.4))
    for i, r in enumerate(res.itertuples()):
        y = len(res) - 1 - i
        ax.plot([r.ci[0] * 100, r.ci[1] * 100], [y, y], color=hs.INK, lw=2)
        ax.plot(r.mean * 100, y, marker="o", color=hs.INK, ms=7)
    ax.axvline(0, color=hs.INK_3, lw=1, ls=(0, (4, 3)))
    ax.set_yticks(range(len(res)))
    ax.set_yticklabels([(labels or {}).get(c, c) for c in res.contrast][::-1])
    ax.set_xlabel("Difference in useful readings per run (percentage points; 95% CI)")
    ax.set_title("Paired contrasts across held-out runs (Holm-corrected p in the table)")
    ax.grid(axis="y", visible=False)
    return fig
