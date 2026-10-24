"""
hinigram_multiperson.py: can one ESP32 link watch several people?
=================================================================
Several simulated people breathe on one real link of the format sample, each with their own rate, distance (modulation
depth 5, 3 or 1.5%) and pattern across the subcarriers, as hinigram_live.inject_breathing models one person. Three ways
of reading the link are compared on the same 30 s windows:

* v1.3.2: the frozen pipeline, one rate per link (what the board shows);
* peaks: the strongest peaks of the breathing-band spectrum of the link's main components, harmonics removed, as many as
  there are people (the number of people is given to it, which no real system knows);
* ICA: the components separated by independent component analysis (FastICA, as many sources as people), one rate each.

Each person counts as found in a window when one estimate lies within +/-2 per minute of their mean rate over the window,
each estimate standing for one person at most (optimal assignment). Windows in which the link shows movement are left out
for every method. Conditions, each on the three links and two backgrounds (the recording's quiet stretch, and all of it,
played forward then backward):

* resting: 1 to 4 adults at 12 to 20 per minute;
* fast: one person at 26 to 32 per minute among 1 to 3 at 12 to 20 (can the one who needs attention be found?);
* pause: person 1 stops breathing for 20 s at 150 s while the others go on: does v1.3.2 raise its pause alert, and how
  often does it say "no breathing concern" during the pause (runs with movement around the pause are left out). The
  peaks and ICA readers give rates, not pauses, so only v1.3.2 is scored here.

The patterns of different people are independent random draws, which favours ICA: real bodies close together give more
similar patterns. Read the separation results as an upper bound.

    python hinigram_multiperson.py [trials]     (default 20 per condition; about 25 minutes on four cores)
writes results/multiperson_windows.csv.gz, multiperson_rates.csv, multiperson_pause.csv and multiperson.png

    python hinigram_multiperson.py hku [folder]      (default: training/hku, from hku_adapter.py)
runs the same readers on the HKU set's two real two-person recordings: results/multiperson_hku.csv
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__":
    for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):    # one maths thread per worker
        os.environ.setdefault(_v, "1")

import warnings

import numpy as np
import pandas as pd
from scipy import signal as sig
from scipy.optimize import linear_sum_assignment

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:
    sys.path.append(os.path.dirname(HERE))
import hinigram_live as hl

SAMPLE = os.path.join(os.path.dirname(HERE), "demo_20261019_024431.csv")
RESULTS = os.path.join(HERE, "results")
BACKGROUNDS = {"quiet": (112.0, 173.3), "busy": (0.0, 173.3)}   # the recording's stretch without movement, and all of it
DUR, WIN, HOP, FS = 240.0, 30.0, 4.0, 10.0
DEPTHS = (0.05, 0.03, 0.015)
PAUSE = (150.0, 170.0)
DATA = hl.ESP32_LLTF_DATA_SLOTS
KK = hl.ESP32_SLOT_TO_SUBCARRIER.astype(float) / 26.0
BAND = (0.10, 0.75)                                            # adult band of v1.3.2 (6 to 45 per minute)


def looped(L: hl.LinkStream, a: float, b: float, dur: float) -> hl.LinkStream:
    """The link's packets in [a, b), played forward, then backward, and so on, for ``dur`` seconds."""
    m = (L.t >= a) & (L.t < b)
    t, D = L.t[m] - a, b - a
    idx0 = np.flatnonzero(m)
    ts, ii, off, k = [], [], 0.0, 0
    while off < dur:
        if k % 2 == 0:
            ts.append(t + off); ii.append(idx0)
        else:
            ts.append(D - t[::-1] + off); ii.append(idx0[::-1])
        off += D; k += 1
    t2, i2 = np.concatenate(ts), np.concatenate(ii)
    keep = t2 < dur
    t2, i2 = t2[keep], i2[keep]
    return hl.LinkStream(mac=L.mac, t=t2, t_host=np.full(len(t2), np.nan), seq=np.arange(len(t2)), rssi=L.rssi[i2],
                         channel=L.channel[i2], noise_floor=L.noise_floor[i2], first_word_invalid=L.first_word_invalid[i2],
                         H=L.H[i2], label=L.label)


def person(seed: int, segments, depth: float):
    sc = hl.BreathingScenario(segments=segments, depth=depth, phase_depth=depth, seed=seed)
    rng = np.random.default_rng(1000 + seed)
    th1, th2 = rng.uniform(0, 2 * np.pi, 2)
    c1, c2 = rng.uniform(0.6, 1.6, 2)
    w_amp = sc.common_mode + (1 - sc.common_mode) * np.cos(np.pi * c1 * KK + th1)
    w_ph = np.cos(np.pi * c2 * KK + th2)
    return sc, w_amp, w_ph


def modulate(L: hl.LinkStream, people) -> hl.LinkStream:
    """Every person's breathing on the link's packets (amplitude and phase), re-quantised to int8 as the ESP32 reports."""
    mod = np.ones((len(L.t), 64), complex)
    for sc, wa, wp in people:
        b = hl.breathing_waveform(L.t, sc)[0][:, None]
        mod[:, DATA] *= (1 + sc.depth * wa[DATA][None, :] * b) * np.exp(1j * sc.phase_depth * wp[DATA][None, :] * b)
    fwi = L.first_word_invalid.astype(bool)
    mod[fwi, 0:2] = 1
    H = L.H.astype(np.complex128) * mod
    with np.errstate(invalid="ignore"):
        Hq = np.clip(np.round(H.real), -127, 127) + 1j * np.clip(np.round(H.imag), -127, 127)
    Hq = np.where(np.isnan(H), H, Hq)
    out = hl.LinkStream(**{**L.__dict__, "H": Hq.astype(np.complex64)})
    return out


def _band_spectra(Xw: np.ndarray, n_pcs: int = 6):
    sos = sig.butter(3, BAND, btype="band", fs=FS, output="sos")
    Xf = sig.sosfiltfilt(sos, Xw - Xw.mean(axis=0), axis=0)
    sd = Xf.std(axis=0)
    keep = sd > 1e-9
    Z = Xf[:, keep] / sd[keep]
    U, s, _ = np.linalg.svd(Z, full_matrices=False)
    return U[:, :n_pcs] * s[:n_pcs], s[:n_pcs] ** 2 / np.sum(s ** 2)


NFFT = 8192
F_AX = np.fft.rfftfreq(NFFT, 1 / FS)
IN_BAND = (F_AX >= BAND[0]) & (F_AX <= BAND[1])


def _spectrum(x: np.ndarray) -> np.ndarray:
    P = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(len(x)), NFFT)) ** 2
    return P[IN_BAND] / (P[IN_BAND].sum() + 1e-12)


def peaks_rates(Xw: np.ndarray, k: int) -> list:
    """Up to ``k`` rates (per minute): the strongest peaks of the variance-weighted spectrum of the main components,
    a peak dropped when it sits at twice or three times the frequency of a stronger one."""
    pcs, w = _band_spectra(Xw)
    P = sum(wi * _spectrum(pcs[:, i]) for i, wi in enumerate(w))
    f = F_AX[IN_BAND]
    idx, _ = sig.find_peaks(P, prominence=0.05 * P.max())
    idx = idx[np.argsort(P[idx])[::-1]]
    out = []
    for i in idx:
        if P[i] < 0.15 * P[idx[0]]:
            break
        if any(abs(f[i] - h * g) < 0.03 for g in out for h in (2, 3)):
            continue
        out.append(f[i])
        if len(out) == k:
            break
    return [60 * x for x in out]


def ica_rates(Xw: np.ndarray, k: int) -> list:
    """One rate per source separated by FastICA (``k`` sources) from the main components."""
    from sklearn.decomposition import FastICA
    pcs, _ = _band_spectra(Xw)
    if k == 1:
        S = pcs[:, :1]
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            S = FastICA(n_components=k, whiten="unit-variance", random_state=0, max_iter=500).fit_transform(pcs)
    f = F_AX[IN_BAND]
    out = []
    for c in range(S.shape[1]):
        P = _spectrum(S[:, c])
        i = int(np.argmax(P))
        half = np.argmin(np.abs(f - f[i] / 2))           # a breathing harmonic: prefer the fundamental if it is there
        if f[i] / 2 >= BAND[0] and P[half] >= 0.4 * P[i]:
            i = int(half)
        out.append(60 * f[i])
    return out


def match(truth: list, est: list) -> tuple:
    """Optimal one-to-one assignment; returns (found flags per person, spurious estimates)."""
    found = [False] * len(truth)
    if not est or not truth:
        return found, len(est)
    C = np.abs(np.subtract.outer(np.asarray(truth), np.asarray(est)))
    r, c = linear_sum_assignment(C)
    used = 0
    for i, j in zip(r, c):
        if C[i, j] <= 2.0:
            found[i] = True
            used += 1
    return found, len(est) - used


def window_truth(sc: hl.BreathingScenario, te: float) -> float:
    tg = np.arange(te - WIN, te, 0.05)
    bpm = hl.breathing_waveform(tg, sc)[1]
    return float(bpm[bpm > 0].mean()) if np.mean(bpm > 0) >= 0.8 else np.nan


def run(job: dict) -> list:
    S = hl.load_csi_session(SAMPLE)
    L0 = S.links[sorted(S.links)[job["link"]]]
    a, b = BACKGROUNDS[job["bg"]]
    L = looped(L0, a, b, DUR + 2)
    rng = np.random.default_rng(job["seed"])
    n, cond = job["n"], job["cond"]
    rates = list(rng.uniform(12, 20, n))
    if cond == "fast":
        rates[0] = float(rng.uniform(26, 32))
    people = []
    for k in range(n):
        seg = [(0, PAUSE[0], rates[k]), (PAUSE[0], PAUSE[1], 0.0), (PAUSE[1], DUR + 5, rates[k])] if cond == "pause" and k == 0 \
            else [(0, DUR + 5, rates[k])]
        people.append(person(job["seed"] * 10 + k, seg, float(rng.choice(DEPTHS))))
    L2 = modulate(L, people)
    F = hl.link_features(L2, fs=FS, t_end=DUR)
    trk = hl.track_link(F, hl.RRConfig())
    rows = []
    base = dict(cond=cond, n=n, bg=job["bg"], link=job["link"], trial=job["trial"], depths=",".join(f"{p[0].depth:.3f}" for p in people),
                rates=",".join(f"{r:.1f}" for r in rates))
    if cond == "pause":
        m = (trk.t >= PAUSE[0] + 12) & (trk.t <= PAUSE[1] + 2)
        pause_alert = [s == "urgent" and r.startswith("Possible breathing pause") for s, r in zip(trk.status, trk.reason)]
        alert = bool(np.any(np.asarray(pause_alert)[(trk.t >= PAUSE[0]) & (trk.t <= PAUSE[1] + 8)]))
        typical = float(np.mean([trk.status[i] == "typical" for i in np.flatnonzero(m)])) if m.any() else np.nan
        moving = bool(np.any(trk.motion[(trk.t >= PAUSE[0] - 2) & (trk.t <= PAUSE[1])]))
        d = [p[0].depth for p in people]
        rows.append(dict(base, pause_alert=alert, no_concern_share=typical, moving=moving,
                         paused_strongest=bool(d[0] >= max(d)), others_within2=bool(any(abs(r - rates[0]) <= 2 for r in rates[1:]))))
        return rows
    for te in np.arange(WIN + 2, DUR - 1, HOP):
        i1 = np.searchsorted(F.t, te)
        i0 = i1 - int(WIN * FS)
        if i0 < 0 or np.any(F.activity[i0:i1] > 1.0):
            continue                                            # movement on the link: no method is scored here
        truth = [window_truth(p[0], te) for p in people]
        if any(not np.isfinite(x) for x in truth):
            continue
        Xw = F.X[i0:i1]
        j = int(np.argmin(np.abs(trk.t - te)))
        v132 = [float(trk.bpm[j])] if trk.reliable[j] and np.isfinite(trk.bpm[j]) and abs(trk.t[j] - te) <= 1.0 else []
        for meth, est in (("v1.3.2", v132), ("peaks", peaks_rates(Xw, n)), ("ica", ica_rates(Xw, n))):
            found, spur = match(truth, est)
            rows.append(dict(base, t=float(te), method=meth, n_est=len(est), found=sum(found), spurious=spur,
                             first_found=bool(found[0]), collide=bool(n > 1 and min(abs(a - b) for i, a in enumerate(truth) for b in truth[i + 1:]) <= 2)))
    return rows


def jobs(trials: int) -> list:
    out, seed = [], 0
    for cond, ns in (("resting", (1, 2, 3, 4)), ("fast", (2, 3, 4)), ("pause", (1, 2, 3))):
        for n in ns:
            for bg in BACKGROUNDS:
                for link in range(3):
                    for trial in range(trials):
                        seed += 1
                        out.append(dict(cond=cond, n=n, bg=bg, link=link, trial=trial, seed=seed))
    return out


def summarise(df: pd.DataFrame, pz: pd.DataFrame):
    w = df.copy()
    w["people"] = w["n"]
    w["everyone"] = w["found"] == w["n"]
    g = w.groupby(["cond", "bg", "n", "method"])
    rates = pd.DataFrame({
        "windows": g.size(),
        "people_found_pct": 100 * g["found"].sum() / g["people"].sum(),
        "everyone_found_pct": 100 * g["everyone"].mean(),
        "fast_person_found_pct": 100 * g["first_found"].mean(),
        "spurious_per_window": g["spurious"].mean(),
        "windows_with_collision_pct": 100 * g["collide"].mean(),
    }).reset_index()
    rates.loc[rates.cond != "fast", "fast_person_found_pct"] = np.nan
    agg = dict(runs=("pause_alert", "size"), pause_alert_pct=("pause_alert", lambda x: 100 * x.mean()),
               no_concern_during_pause_pct=("no_concern_share", lambda x: 100 * np.nanmean(x)), runs_with_movement=("moving", "sum"))
    q = pz[~pz.moving]                                           # a pause cannot be measured through movement
    pause = pd.concat([q.groupby(["bg", "n"]).agg(**agg).reset_index().assign(paused_person="any"),
                       q[q.n > 1].groupby(["bg", "n", "paused_strongest"]).agg(**agg).reset_index()
                       .assign(paused_person=lambda d: np.where(d.paused_strongest, "strongest on the link", "weaker than another"))
                       .drop(columns="paused_strongest")], ignore_index=True).sort_values(["bg", "n", "paused_person"])
    return rates.round(1), pause.round(1)


def figure(rates: pd.DataFrame, path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    try:
        import hinigram_style as hs
        hs.use_style(download_fonts=False)
    except Exception:
        pass
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, bg in zip(axes, ("quiet", "busy")):
        d = rates[(rates.cond == "resting") & (rates.bg == bg)]
        for meth, ls in (("v1.3.2", "-"), ("peaks", "--"), ("ica", ":")):
            x = d[d.method == meth]
            ax.plot(x.n, x.people_found_pct, ls, marker="o", label={"v1.3.2": "v1.3.2 (one rate per link)", "peaks": "spectral peaks", "ica": "ICA"}[meth])
        ax.set_title({"quiet": "Quiet background", "busy": "Background with movement"}[bg])
        ax.set_xlabel("people on one link")
        ax.set_xticks([1, 2, 3, 4])
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("people whose rate is found (%)")
    axes[0].legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run_hku(folder: str) -> pd.DataFrame:
    """The same three readers on the HKU set's two-person recordings (hku_adapter.py output), each link on v1.3.2's
    2 s grid, against the mean of each person's belt over the window. Two recordings of 34 and 43 s: a handful of
    windows, a check that separation happens on real bodies at all, not a measure of how often."""
    import json
    ref = json.load(open(os.path.join(folder, "hku_reference.json")))
    rows = []
    for rec in (r for r in ref["recordings"] if r["people"] == 2):
        S = hl.load_csi_session(os.path.join(folder, rec["file"]))
        belts = [np.asarray(b, float) for b in rec["belt_bpm_per_s"]]
        for j, mac in enumerate(S.macs):
            F = hl.link_features(S.links[mac], fs=FS)
            trk = hl.track_link(F, hl.RRConfig())
            for te in np.arange(WIN, F.t[-1] + 1e-6, 2.0):
                i1 = int(np.searchsorted(F.t, te + 1e-6))
                i0 = i1 - int(WIN * FS)
                truth = [float(b[max(int(np.ceil(te - WIN)), 0):int(np.floor(te))].mean()) for b in belts]
                if i0 < 0 or np.any(F.activity[i0:i1] > 1.0) or not all(np.isfinite(truth)):
                    continue
                Xw = F.X[i0:i1]
                k = int(np.argmin(np.abs(trk.t - te)))
                v132 = [float(trk.bpm[k])] if trk.reliable[k] and np.isfinite(trk.bpm[k]) and abs(trk.t[k] - te) <= 1.0 else []
                for meth, est in (("v1.3.2", v132), ("peaks", peaks_rates(Xw, 2)), ("ica", ica_rates(Xw, 2))):
                    found, spur = match(truth, est)
                    rows.append(dict(recording=rec["name"], link=rec["link_names"][j], t=float(te), method=meth,
                                     truth=",".join(f"{x:.1f}" for x in truth), est=",".join(f"{x:.1f}" for x in est),
                                     found=sum(found), both=all(found), spurious=spur))
    df = pd.DataFrame(rows)
    os.makedirs(RESULTS, exist_ok=True)
    df.to_csv(os.path.join(RESULTS, "multiperson_hku_windows.csv"), index=False)
    out = df.groupby(["recording", "method"]).agg(windows=("found", "size"), people_found_pct=("found", lambda x: 50 * x.mean()),
                                                  both_found_pct=("both", lambda x: 100 * x.mean())).round(1).reset_index()
    out["recording"] = out.recording.str.extract(r"bpm([\d-]+)")[0] + " per minute"
    out.to_csv(os.path.join(RESULTS, "multiperson_hku.csv"), index=False)
    print(out.to_string(index=False))
    return out


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "hku":
    run_hku(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "hku"))
elif __name__ == "__main__":
    from multiprocessing import Pool
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    J = jobs(trials)
    workers = int(os.environ.get("HINIGRAM_WORKERS", "4"))
    with Pool(workers) as pool:
        rows = [r for rs in pool.imap_unordered(run, J, chunksize=2) for r in rs]
    df = pd.DataFrame(rows)
    os.makedirs(RESULTS, exist_ok=True)
    win = df[df.cond != "pause"].dropna(axis=1, how="all")
    pz = df[df.cond == "pause"].dropna(axis=1, how="all")
    pz = pz.astype({k: bool for k in ("pause_alert", "moving", "paused_strongest", "others_within2")})   # mixed with window rows above
    win.to_csv(os.path.join(RESULTS, "multiperson_windows.csv.gz"), index=False)
    rates, pause = summarise(win, pz)
    rates.to_csv(os.path.join(RESULTS, "multiperson_rates.csv"), index=False)
    pause.to_csv(os.path.join(RESULTS, "multiperson_pause.csv"), index=False)
    pz.to_csv(os.path.join(RESULTS, "multiperson_pause_runs.csv"), index=False)
    figure(rates, os.path.join(RESULTS, "multiperson.png"))
    print(rates.to_string(index=False))
    print(pause.to_string(index=False))
