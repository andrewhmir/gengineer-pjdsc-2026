"""
hinigram_dataset.py  (Hinigram v1.3.2, training data for learned estimators)
===========================================================================
Semi-synthetic training, validation and test data built on the real format sample.

The stages are separate functions so each can be checked on its own:

1. ``sample_scenario``  per link: an age profile, a piecewise breathing-rate programme (sometimes a
   rate change, sometimes a pause) and a modulation depth.
2. ``inject``           known breathing modulated onto every packet of the real recording
                        (``hinigram_live.inject_breathing``: loss, timing jitter and gain steps kept).
3. ``preprocess``       the DSP pipeline's own parsing, per-MAC split, receiver clock, per-packet
                        cleaning, 10 Hz resampling and Hampel filter (``hinigram_live.link_features``).
4. ``window_index``     30 s windows ending at exactly the DSP's hop times, so every model and the
                        DSP are scored on the same windows.
5. ``labels``           mean programmed rate where breathing fills the window, breathing present in the
                        newest 6 s, and the true screening state.
6. ``dsp_reference``    the frozen v1.3.2 track for the same link (rate, reliability, state, and the
                        pause, motion and recency signals the screening state machine needs).

Each file is cached as one ``.npz`` (features per link, labels and DSP outputs per window); the CSV is
deleted afterwards because it can be regenerated exactly from its seed. Model inputs are cut from the
cached features on the fly (``model_input``) using only samples inside the window, so nothing from the
future leaks into a window.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

if __name__ == "__main__":      # one maths thread per worker process: several workers each running a multi-threaded
    for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):    # BLAS fight over the cores (about 50x slower)
        os.environ.setdefault(_v, "1")

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:        # bundle: training/ sits next to the pipeline modules
    sys.path.append(os.path.dirname(HERE))
import hinigram_live as hl

SRC = next((p for p in (os.path.join(HERE, "demo_20261019_024431.csv"), os.path.join(os.path.dirname(HERE), "demo_20261019_024431.csv"),
                        "/mnt/user-data/uploads/demo_20261019_024431.csv") if os.path.exists(p)), "demo_20261019_024431.csv")
MACS = ["1a:00:00:00:00:01", "1a:00:00:00:00:02", "1a:00:00:00:00:03"]
PROFILES = ["adult", "child_1_5y", "infant_2_12m", "newborn_lt2m"]
FS, WIN_S, HOP_S, RECENT_S = 10.0, 30.0, 2.0, 6.0
NW, NH, NREC = int(WIN_S * FS), int(HOP_S * FS), int(RECENT_S * FS)

# training rates stay inside each profile's analysis band in hinigram_live.RRConfig
RATE_RANGE = {"adult": (6.5, 42.0), "child_1_5y": (10.0, 58.0), "infant_2_12m": (13.0, 70.0), "newborn_lt2m": (16.0, 82.0)}
PROFILE_P = [0.5, 0.2, 0.2, 0.1]
DEPTH_RANGE = (0.012, 0.07)

# held-out set 5: the eleven held-out scenarios of hinigram_eval, depths rotated so every link gets every depth
TEST_DEPTHS = [0.05, 0.03, 0.015]


# --------------------------------------------------------------------------- 1. scenarios
def sample_scenario(rng: np.random.Generator, t_max: float = 180.0) -> Tuple[list, str, float]:
    """(segments, profile, depth) for one link. Segments are (t0, t1, breaths/min); 0 means a pause."""
    prof = PROFILES[rng.choice(len(PROFILES), p=PROFILE_P)]
    lo, hi = RATE_RANGE[prof]
    r0 = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
    cuts = [(0.0, r0)]
    if rng.random() < 0.4:                       # a rate change part-way through
        tc = float(rng.uniform(40, 140))
        r1 = float(np.clip(r0 * np.exp(rng.normal(0, 0.3)), lo, hi))
        cuts.append((tc, r1))
    segs = []
    for k, (ts, r) in enumerate(cuts):
        te = cuts[k + 1][0] if k + 1 < len(cuts) else t_max
        segs.append((ts, te, r))
    if rng.random() < 0.35:                      # a pause of 4 to 30 s
        d = float(rng.uniform(4, 30))
        a = float(rng.uniform(25, 170 - d))
        out = []
        for s0, s1, r in segs:
            if s1 <= a or s0 >= a + d:
                out.append((s0, s1, r))
                continue
            if s0 < a:
                out.append((s0, a, r))
            if s1 > a + d:
                out.append((a + d, s1, r))
        out.append((a, a + d, 0.0))
        segs = sorted(out)
    depth = float(np.exp(rng.uniform(np.log(DEPTH_RANGE[0]), np.log(DEPTH_RANGE[1]))))
    return segs, prof, depth


def random_file_spec(seed: int) -> dict:
    """Independent scenario per link (three different people)."""
    rng = np.random.default_rng(seed)
    links = []
    for i, mac in enumerate(MACS):
        segs, prof, depth = sample_scenario(rng)
        links.append(dict(mac=mac, segments=segs, profile=prof, depth=depth, seed=seed * 10 + i))
    return dict(name=f"rand_s{seed}", seed=seed, links=links)


def heldout5_specs(seeds=(51, 52)) -> List[dict]:
    import hinigram_eval as he
    specs = []
    for seed in seeds:
        for name, (segs, prof) in he.SCENARIOS.items():
            for rot in range(3):
                links = [dict(mac=mac, segments=list(segs), profile=prof, depth=TEST_DEPTHS[(i + rot) % 3],
                              seed=seed * 100 + rot * 10 + i) for i, mac in enumerate(MACS)]
                specs.append(dict(name=f"{name}_r{rot}_s{seed}", scenario=name, rot=rot, seed=seed, links=links))
    return specs


def scenarios_of(spec: dict) -> Dict[str, hl.BreathingScenario]:
    return {L["mac"]: hl.BreathingScenario(L["segments"], depth=L["depth"], phase_depth=L["depth"], seed=L["seed"], name=spec["name"])
            for L in spec["links"]}


# --------------------------------------------------------------------------- 2-6. one file
def inject(spec: dict, csv_path: str) -> Dict[str, hl.BreathingScenario]:
    scs = scenarios_of(spec)
    hl.inject_breathing(SRC, csv_path, scs)
    return scs


def window_ends(T: int) -> np.ndarray:
    """Same hop grid as hinigram_live.track_link: windows [e - NW, e)."""
    return np.arange(NW, T + 1, NH)


def labels_for(sc: Optional[hl.BreathingScenario], t: np.ndarray, ends: np.ndarray, profile: str) -> dict:
    n = len(ends)
    if sc is None:                               # the raw recording: no reference
        nan = np.full(n, np.nan)
        return dict(rate=nan, frac=nan, present=np.full(n, -1, np.int8), truth_status=["absent"] * n)
    from validate_heldout import truth_status
    _, bpm = hl.breathing_waveform(t, sc)
    rate, frac, present, ts = np.full(n, np.nan), np.zeros(n), np.full(n, -1, np.int8), []
    for k, e in enumerate(ends):
        b = bpm[e - NW:e]
        on = b > 0
        frac[k] = on.mean()
        if frac[k] >= 0.98:
            rate[k] = float(b[on].mean())
        rec = on[-NREC:]
        present[k] = 1 if rec.all() else (0 if not rec.any() else -1)
        ts.append(truth_status(sc, float(t[e - 1]), profile))
    return dict(rate=rate, frac=frac, present=present, truth_status=ts)


def process(csv_path: str, scs: Optional[Dict[str, hl.BreathingScenario]], profiles: Dict[str, str]) -> dict:
    """Preprocess every link, cut the window grid, attach labels and the DSP reference."""
    S = hl.load_csi_session(csv_path)
    t_end = min(float(L.t[-1]) for L in S.links.values())
    out = dict(links=[])
    for mac in MACS:
        F = hl.link_features(S.links[mac], fs=FS, t_end=t_end)
        prof = profiles[mac]
        trk = hl.track_link(F, hl.RRConfig(profile=prof))
        ends = window_ends(len(F.t))
        assert len(ends) == len(trk.t) and np.allclose(F.t[ends - 1], trk.t), "window grid differs from the DSP"
        lab = labels_for(scs[mac] if scs else None, F.t, ends, prof)
        out["links"].append(dict(
            mac=mac, profile=prof, t=F.t.astype(np.float32), X=F.X.astype(np.float32), activity=F.activity.astype(np.float32),
            gap=F.gap.astype(bool), ends=ends.astype(np.int32), **lab,
            dsp=dict(bpm=trk.bpm, raw=trk.bpm_raw, reliable=trk.reliable, motion=trk.motion, quality=trk.quality,
                     prominence=trk.prominence, acf=trk.acf, status=np.array(trk.status), reason=np.array(trk.reason),
                     pause_s=trk.pause_s, quiet=trk.resp_rms_ratio, snr=trk.pause_snr, period=trk.base_period,
                     recent_ratio=trk.recent_ratio, recent_low=trk.recent_low, recent_gated=trk.recent_gated)))
    return out


def save_npz(path: str, spec: dict, data: dict) -> None:
    arrays = {"spec": np.array(json.dumps(spec))}
    for i, L in enumerate(data["links"]):
        for k, v in L.items():
            if k == "dsp":
                for dk, dv in v.items():
                    arrays[f"l{i}_dsp_{dk}"] = np.asarray(dv)
            elif k == "truth_status":
                arrays[f"l{i}_{k}"] = np.array(v)
            else:
                arrays[f"l{i}_{k}"] = np.asarray(v)
    np.savez_compressed(path, **arrays)


def load_npz(path: str) -> dict:
    z = np.load(path, allow_pickle=False)
    spec = json.loads(str(z["spec"]))
    links = []
    for i in range(len(MACS)):
        L = {k[len(f"l{i}_"):]: z[k] for k in z.files if k.startswith(f"l{i}_") and not k.startswith(f"l{i}_dsp_")}
        L["dsp"] = {k[len(f"l{i}_dsp_"):]: z[k] for k in z.files if k.startswith(f"l{i}_dsp_")}
        L["mac"] = str(L["mac"]); L["profile"] = str(L["profile"])
        links.append(L)
    return dict(spec=spec, links=links)


def build(spec: dict, out_dir: str, tmp_dir: str) -> str:
    """Inject, preprocess and cache one file; returns the .npz path (skips work already done)."""
    os.makedirs(out_dir, exist_ok=True); os.makedirs(tmp_dir, exist_ok=True)
    dst = os.path.join(out_dir, spec["name"] + ".npz")
    if os.path.exists(dst):
        return dst
    csv = os.path.join(tmp_dir, spec["name"] + ".csv")
    scs = inject(spec, csv)
    data = process(csv, scs, {L["mac"]: L["profile"] for L in spec["links"]})
    save_npz(dst + ".part.npz", spec, data)
    os.replace(dst + ".part.npz", dst)
    os.remove(csv)
    return dst


def build_raw(out_dir: str) -> str:
    """The unmodified recording, once per profile, for the null test."""
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "raw_adult.npz")
    if not os.path.exists(dst):
        spec = dict(name="raw_adult", seed=0, links=[dict(mac=m, segments=[], profile="adult", depth=0.0, seed=0) for m in MACS])
        save_npz(dst, spec, process(SRC, None, {m: "adult" for m in MACS}))
    return dst


# --------------------------------------------------------------------------- model input
_BASIS = {}


def _detrend_basis(n: int) -> np.ndarray:
    if n not in _BASIS:
        tt = np.linspace(-1, 1, n)
        B, _ = np.linalg.qr(np.stack([np.ones(n), tt], 1))
        _BASIS[n] = B.astype(np.float32)
    return _BASIS[n]


def model_input(X: np.ndarray, ends: np.ndarray, clip: float = 5.0) -> np.ndarray:
    """(n, NW, C) windows: per window and channel, remove mean and linear trend, divide by the SD.

    Uses only samples inside each window (causal at the window end), like the DSP.
    """
    idx = ends[:, None] - NW + np.arange(NW)[None, :]
    W = X[idx]                                           # (n, NW, C)
    B = _detrend_basis(NW)
    W = W - np.einsum("tk,nkc->ntc", B, np.einsum("tk,ntc->nkc", B, W))
    sd = W.std(axis=1, keepdims=True)
    W = np.where(sd > 1e-6, W / np.maximum(sd, 1e-6), 0.0)
    return np.clip(W, -clip, clip).astype(np.float32)



# --------------------------------------------------------------------------- model inputs (shared by every learned arm)
DEC = 2                                    # the 10 Hz window averaged in pairs to 5 Hz (breathing stays under 1.5 Hz)
T_WIN, DT, SKIP = NW // DEC, DEC / FS, 15  # 150 samples, 0.2 s, the first 3 s skipped by the oscillator readouts
N_PC, N_OSC = 4, 16                        # principal components per window; oscillators per bank


def _band_sos(profile: str):
    import scipy.signal as sig
    lo, hi = hl_band(profile)
    fs = FS / DEC
    return sig.butter(3, [lo * 0.8, min(hi * 1.15, 0.45 * fs)], btype="bandpass", fs=fs, output="sos")


def hl_band(profile: str):
    return hl.RRConfig(profile=profile).band_hz


_SOS = {}


def window_inputs(X: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """(n, T_WIN, C): each 30 s window averaged in pairs to 5 Hz, each channel detrended and scaled to unit SD (clipped at 5)."""
    B = _detrend_basis(T_WIN)
    W = X[ends[:, None] - NW + np.arange(NW)[None, :]]
    W = W.reshape(len(ends), T_WIN, DEC, W.shape[2]).mean(axis=2)
    W = W - np.einsum("tk,nkc->ntc", B, np.einsum("tk,ntc->nkc", B, W))
    sd = W.std(axis=1, keepdims=True)
    return np.clip(np.where(sd > 1e-6, W / np.maximum(sd, 1e-6), 0.0), -5, 5).astype(np.float32)


def pca_components(W: np.ndarray, prof_idx: np.ndarray, k: int = N_PC) -> np.ndarray:
    """Per window: band-pass by age profile (zero-phase, inside the window only, as the DSP does), PCA over the
    channels, keep the top k component series scaled to unit variance, sign fixed so the third moment is positive."""
    import scipy.signal as sig
    out = np.empty((W.shape[0], W.shape[1], k), np.float32)
    for pi in np.unique(prof_idx):
        m = prof_idx == pi
        if pi not in _SOS:
            _SOS[pi] = _band_sos(PROFILES[pi])
        Wf = sig.sosfiltfilt(_SOS[pi], W[m], axis=1)
        Wf = Wf - Wf.mean(axis=1, keepdims=True)
        U, S, _ = np.linalg.svd(Wf, full_matrices=False)
        P = U[:, :, :k] * S[:, None, :k]
        P = P / (P.std(axis=1, keepdims=True) + 1e-9)
        sgn = np.sign(np.mean(P ** 3, axis=1, keepdims=True))
        out[m] = (P * np.where(sgn == 0, 1.0, sgn)).astype(np.float32)
    return out


def pc_cache(path: str) -> list:
    """Model inputs for every window of every link of one cached file: (n_windows, T_WIN, N_PC) per link.

    Computed once (decimate to 5 Hz, detrend, standardise, band-pass by profile, PCA) and stored next to the
    file in a pc/ folder; uses only samples inside each window."""
    cdir = os.path.join(os.path.dirname(path), "pc")
    cpath = os.path.join(cdir, os.path.basename(path))
    if os.path.exists(cpath):
        z = np.load(cpath)
        return [z[f"l{i}"] for i in range(len(MACS))]
    d = load_npz(path)
    out = []
    for L in d["links"]:
        ends = L["ends"].astype(np.int64)
        out.append(pca_components(window_inputs(L["X"], ends), np.full(len(ends), PROFILES.index(str(L["profile"])))))
    os.makedirs(cdir, exist_ok=True)
    tmp = cpath + f".{os.getpid()}.tmp.npz"
    np.savez(tmp, **{f"l{i}": a for i, a in enumerate(out)})
    os.replace(tmp, cpath)
    return out


def surrogate_shifts(seed: int) -> np.ndarray:
    """Fixed, oscillator-specific circular shifts (a quarter to three quarters of the readout span)."""
    rng = np.random.default_rng(10_000 + seed)
    n = T_WIN - SKIP
    return rng.integers(n // 4, 3 * n // 4, size=N_OSC)



if __name__ == "__main__":
    import sys
    from concurrent.futures import ProcessPoolExecutor
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    root = os.path.join(HERE, "mldata")
    tmp = os.path.join(HERE, "mldata_tmp")
    jobs = []
    if which in ("train", "all"):
        jobs += [(random_file_spec(s), os.path.join(root, "train")) for s in range(1000, 1150)]
    if which in ("val", "all"):
        jobs += [(random_file_spec(s), os.path.join(root, "val")) for s in range(2000, 2030)]
    if which in ("test", "all"):
        jobs += [(sp, os.path.join(root, "test5")) for sp in heldout5_specs()]
    if which == "test6":                         # fresh held-out set 6 (seeds 61, 62): built only after the fallback rule was frozen
        jobs += [(sp, os.path.join(root, "test6")) for sp in heldout5_specs(seeds=(61, 62))]
    t0 = time.time()
    build_raw(os.path.join(root, "raw"))
    workers = int(os.environ.get("HINIGRAM_WORKERS", "2"))
    with ProcessPoolExecutor(workers) as ex:
        for k, p in enumerate(ex.map(build, [j[0] for j in jobs], [j[1] for j in jobs], [tmp] * len(jobs))):
            if k % 10 == 0:
                print(f"{k + 1}/{len(jobs)} {os.path.basename(p)} {time.time() - t0:.0f}s", flush=True)
    print("done", len(jobs), f"{time.time() - t0:.0f}s")
