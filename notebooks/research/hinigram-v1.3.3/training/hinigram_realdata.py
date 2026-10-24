"""
hinigram_realdata.py: v1.3.2, ResoNet and the fallback rule against a real breathing reference
==============================================================================================
For receiver-format CSVs (any number of sensors, any addresses) with a breathing reference recorded at the same time:

* ``hku``    the HKU AIoT lab dataset converted by hku_adapter.py: a PLUX belt's rate every second, one or two people;
* ``paced``  a recording made while someone breathed with the board's pacer, plus the pacer log the board saved.

For every sensor and every 30 s window on v1.3.2's own 2 s grid it records the reference and what each method shows:

* v1.3.2, frozen: its rate where it shows one, and its screening state;
* ResoNet (the variant in results/fallback_rule.json, both seeds): each fold's model on the window's top four components
  (the training pipeline's own preprocessing), shown at that model's calibrated 95% threshold. A real link belongs to no
  fold, so every metric is computed per (seed, fold) model and then averaged;
* the fallback rule exactly as frozen: v1.3.2 first, then that model only where its frozen conditions hold.

The reference for a window is the mean belt rate over it (the HKU belt gives one rate a second), or the pacer step's rate
when the window lies wholly inside a step, as hinigram_paced.score does. Rates only: with references at 12, 20 and 24 per
minute, half a breath from the adult cut-offs at 11.5, 20.5 and 24.5, a screening-state score would mostly measure jitter.
Real recordings never go through hinigram_dataset.build, which deletes the CSV it works on.

    python hinigram_realdata.py hku [folder with hku_reference.json and hku_*.csv]       (default: training/hku)
    python hinigram_realdata.py paced <recording.csv> <hinigram_pacer_log.json> [profile]
"""
from __future__ import annotations

import datetime
import json
import os
import sys

import numpy as np
import pandas as pd

import hinigram_dataset as hd
import hinigram_live as hl

HERE = hd.HERE
RESULTS = os.path.join(HERE, "results")


def sensor_windows(csv_path: str, profile: str = "adult") -> dict:
    """Per sensor: window end times, v1.3.2's track and the model input (top four components), on v1.3.2's grid."""
    S = hl.load_csi_session(csv_path)
    t_end = min(float(L.t[-1]) for L in S.links.values())
    out = {}
    for mac in S.macs:
        F = hl.link_features(S.links[mac], fs=hd.FS, t_end=t_end)
        if len(F.t) < hd.NW:
            continue
        trk = hl.track_link(F, hl.RRConfig(profile=profile))
        ends = hd.window_ends(len(F.t))
        assert len(ends) == len(trk.t) and np.allclose(F.t[ends - 1], trk.t), "window grid differs from v1.3.2's"
        P = hd.pca_components(hd.window_inputs(F.X.astype(np.float32), ends), np.full(len(ends), hd.PROFILES.index(profile)))
        out[mac] = dict(t=np.asarray(trk.t, float), trk=trk, P=P, profile=profile)
    return dict(session=S, sensors=out)


_MODELS = {}


def model_outputs(P: np.ndarray, profile: str, variant: str, seed: int, fold: int) -> dict:
    """One trained model's rate, predicted SD and breathing-present probability for each window."""
    import jax
    import hinigram_resonet as R
    key = (variant, seed, fold)
    if key not in _MODELS:
        import pickle
        with open(os.path.join(HERE, "mlruns", f"{variant}_f{fold}_s{seed}_params.pkl"), "rb") as fh:     # our own saved weights
            d = pickle.load(fh)
        R.CFG["pool"] = True
        f = jax.jit(lambda p, s, x, prof, k: R.forward(p, s, x, prof, d["arm"], d["shifts"], False, k)[:3])
        cal = json.load(open(os.path.join(HERE, "mlruns", f"{variant}_f{fold}_s{seed}_summary.json")))["calibration"]
        _MODELS[key] = (d, f, cal)
    d, f, cal = _MODELS[key]
    prof = np.eye(R.N_PROF, dtype=np.float32)[np.full(len(P), hd.PROFILES.index(profile))]
    mu, ls, pl = (np.asarray(a) for a in f(d["params"], d["state"], P.astype(np.float32), prof, jax.random.PRNGKey(7)))
    tau = cal["tau"] if cal["val_coverage"] > 0 else -np.inf
    return dict(rate=np.exp(mu), sd=np.exp(ls), p_present=1 / (1 + np.exp(-pl)), tau=tau)


def methods(w: dict, rule: dict) -> list:
    """(method, seed, fold, rate shown or NaN) for one sensor's windows."""
    trk = w["trk"]
    dsp_rel = np.asarray(trk.reliable, bool)
    dsp = np.where(dsp_rel, np.asarray(trk.bpm, float), np.nan)
    out = [("v1.3.2", -1, -1, dsp)]
    r = rule["rule"]
    for seed in (0, 1):
        for fold in range(3):
            m = model_outputs(w["P"], w["profile"], r["variant"], seed, fold)
            shown = (m["p_present"] > 0.5) & (m["sd"] <= m["tau"])
            out.append(("model", seed, fold, np.where(shown, m["rate"], np.nan)))
            tf = r["validation"][r["variant"]][f"s{seed}_f{fold}"]["tau"]
            tf = -np.inf if tf is None else tf
            add = (~dsp_rel) & (~np.asarray(trk.motion, bool)) & (~np.asarray(trk.recent_low, bool)) & (m["p_present"] > 0.5) & (m["sd"] <= tf)
            out.append(("fallback", seed, fold, np.where(dsp_rel, dsp, np.where(add, m["rate"], np.nan))))
    return out


def score_rows(name, mac, t, refs, ests) -> list:
    """refs: list of reference arrays (one per person). A reading is right if within 2/min of any person's reference."""
    has = np.any([np.isfinite(r) for r in refs], axis=0)
    rows = []
    for meth, seed, fold, est in ests:
        shown = has & np.isfinite(est)
        errs = np.min([np.abs(est - r) for r in refs], axis=0)
        ok = shown & (errs <= 2)
        rows.append(dict(recording=name, sensor=mac, method=meth, seed=seed, fold=fold, windows=int(has.sum()), shown=int(shown.sum()),
                         within2=int(ok.sum()), abs_err_sum=float(np.nansum(np.where(shown, errs, 0.0))),
                         person1=int((shown & (np.abs(est - refs[0]) <= 2)).sum()),
                         person2=int((shown & (np.abs(est - refs[1]) <= 2)).sum()) if len(refs) > 1 else None))
    return rows


def summarise(rows: pd.DataFrame, by: list) -> pd.DataFrame:
    """Shares per method; model and fallback averaged over their six (seed, fold) models."""
    g = rows.groupby(by + ["method", "seed", "fold"], dropna=False)[["windows", "shown", "within2", "abs_err_sum"]].sum().reset_index()
    g["shown_pct"] = 100 * g.shown / g.windows.clip(lower=1)
    g["within2_of_shown_pct"] = 100 * g.within2 / g.shown.replace(0, np.nan)
    g["useful_pct"] = 100 * g.within2 / g.windows.clip(lower=1)
    g["mae"] = g.abs_err_sum / g.shown.replace(0, np.nan)
    return g.groupby(by + ["method"], dropna=False)[["windows", "shown_pct", "within2_of_shown_pct", "useful_pct", "mae"]].mean().round(2).reset_index()


def belt_reference(t_end: np.ndarray, belt: np.ndarray) -> np.ndarray:
    """Mean belt rate over each window (t - 30, t]; the belt's rate i covers second [i, i+1) of the recording. NaN
    where less than 90% of the window has a valid rate."""
    r = np.full(len(t_end), np.nan)
    for k, te in enumerate(t_end):
        seg = belt[max(int(np.ceil(te - hd.WIN_S)), 0):min(int(np.floor(te)), len(belt))]
        if len(seg) >= 0.9 * hd.WIN_S and np.all(np.isfinite(seg)) and np.all(seg > 0):
            r[k] = float(seg.mean())
    return r


def load_rule() -> dict:
    return json.load(open(os.path.join(RESULTS, "fallback_rule.json")))


def run_hku(folder: str) -> dict:
    ref = json.load(open(os.path.join(folder, "hku_reference.json")))
    rule = load_rule()
    rows, alerts = [], []
    for rec in ref["recordings"]:
        sw = sensor_windows(os.path.join(folder, rec["file"]))
        belts = [np.asarray(b, float) for b in rec["belt_bpm_per_s"]]
        for mac, w in sw["sensors"].items():
            refs = [belt_reference(w["t"], b) for b in belts]
            rows += score_rows(rec["name"], mac, w["t"], refs, methods(w, rule))
    if "empty" in ref:
        sw = sensor_windows(os.path.join(folder, ref["empty"]["file"]))
        for mac, w in sw["sensors"].items():
            st = np.array(w["trk"].status)
            alerts.append(dict(sensor=mac, windows=len(st), rate_shown=int(np.sum(w["trk"].reliable)),
                               pause_alerts=int(np.sum([s == "urgent" and "pause" in r.lower() for s, r in zip(st, w["trk"].reason)])),
                               states=", ".join(f"{k}: {v}" for k, v in pd.Series(st).value_counts().items())))
    rows = pd.DataFrame(rows)
    os.makedirs(RESULTS, exist_ok=True)
    rows.to_csv(os.path.join(RESULTS, "realdata_hku_rows.csv"), index=False)
    per_rec = summarise(rows, ["recording"])
    pooled_one = summarise(rows[~rows.recording.str.contains("multiperson")].assign(group="one person"), ["group"])
    two = rows[rows.recording.str.contains("multiperson")]
    out = dict(per_recording=per_rec, one_person=pooled_one)
    if len(two):
        # which person's rate a shown reading matches (within 2/min); model and fallback averaged over their six models
        t2 = two.groupby(["method", "seed", "fold"])[["windows", "shown", "person1", "person2"]].sum().reset_index()
        for k in ("shown", "person1", "person2"):
            t2[k + "_pct"] = 100 * t2[k] / (t2.windows if k == "shown" else t2.shown.replace(0, np.nan))
        out["two_people"] = t2.groupby("method")[["windows", "shown_pct", "person1_pct", "person2_pct"]].mean().round(1).reset_index()
    if alerts:
        out["empty_office"] = pd.DataFrame(alerts)
    for k, v in out.items():
        v.to_csv(os.path.join(RESULTS, f"realdata_hku_{k}.csv"), index=False)
        print(f"\n{k}\n" + v.to_string(index=False))
    return out


def run_paced(csv_path: str, log_path: str, profile: str = "adult") -> pd.DataFrame:
    log = json.load(open(log_path, encoding="utf-8"))
    sw = sensor_windows(csv_path, profile)
    S = sw["session"]
    mac = log.get("mac") if log.get("mac") in sw["sensors"] else list(sw["sensors"])[0]
    w = sw["sensors"][mac]
    t0 = datetime.datetime.fromisoformat(log["startedAt"].replace("Z", "+00:00")).timestamp() - S.t0_host
    ref = np.full(len(w["t"]), np.nan)
    for st in log["steps"]:
        if not st.get("rest"):
            m = (w["t"] >= t0 + st["start_s"] + 32) & (w["t"] <= t0 + st["end_s"])      # as hinigram_paced.score
            ref[m] = st["rate"]
    rows = pd.DataFrame(score_rows(os.path.basename(csv_path), mac, w["t"], [ref], methods(w, load_rule())))
    out = summarise(rows, ["recording"])
    print(out.to_string(index=False))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "hku":
        run_hku(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "hku"))
    elif sys.argv[1] == "paced":
        run_paced(*sys.argv[2:5])
    else:
        sys.exit(__doc__)
