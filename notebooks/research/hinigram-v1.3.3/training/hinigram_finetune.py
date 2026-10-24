"""
hinigram_finetune.py: fine-tune the learned estimator on real breathing labels, one recording held out at a time
================================================================================================================
The models were trained on simulated breathing only. With a real reference (the HKU belt, or the board's pacer), the
last layer of each model's head and its batch-norm scales and shifts (740 of its 16,517 weights) are fine-tuned on real windows;
the oscillator bank (97 weights) and the head's first dense layer (15,680) stay as trained, which suits a few minutes of
data. Evaluation is leave-one-recording-out: each
one-person recording is scored by models fine-tuned on the others only, so no window is scored by a model that saw it.

For each held-out recording and each of the six 80-epoch models (two seeds x three folds):
* before: the model as trained on simulated breathing;
* after: the same model with its head fine-tuned on the other recordings' windows (rate as log breaths/min with the
  model's own Gaussian loss, breathing present = 1; 40 full-batch AdamW steps, learning rate 3e-4, weight decay 1e-4).
Reported, averaged over the six models: windows within +/-2 per minute and mean error over every window with a
reference (no abstention), and the share given a rate within +/-2 at the model's own calibrated threshold. Two-person
recordings are left out: their windows have two right answers.

This is a small experiment (the six one-person recordings of the HKU set: about six minutes of one office, probably one person); it shows whether real
labels move the model, not how a fine-tuned model would do in a waiting room. Real data must be split by person and
by session, never by window.

    python hinigram_finetune.py hku [folder with hku_reference.json]      (default: training/hku)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

import hinigram_dataset as hd
import hinigram_realdata as rd

HERE = hd.HERE
TUNED = ("bn_g", "bn_b", "W2", "b2")          # batch-norm scale and shift, and the output layer
STEPS, LR, WD = 40, 3e-4, 1e-4


def hku_recordings(folder: str) -> list:
    """One entry per one-person recording: every sensor's windows (top four components) with the belt's window rate."""
    ref = json.load(open(os.path.join(folder, "hku_reference.json")))
    out = []
    for rec in ref["recordings"]:
        if rec["people"] != 1:
            continue
        sw = rd.sensor_windows(os.path.join(folder, rec["file"]))
        belt = np.asarray(rec["belt_bpm_per_s"][0], float)
        P, y = [], []
        for mac, w in sw["sensors"].items():
            P.append(w["P"]); y.append(rd.belt_reference(w["t"], belt))
        out.append(dict(name=rec["name"], P=np.concatenate(P).astype(np.float32), rate=np.concatenate(y)))
    return out


def _batch(R, P, rate):
    has = np.isfinite(rate)
    return dict(x=P, prof=np.eye(R.N_PROF, dtype=np.float32)[np.zeros(len(P), int)],     # adults
                y=np.where(has, np.log(np.where(has, rate, 1.0)), 0.0).astype(np.float32), my=has.astype(np.float32),
                pres=np.ones(len(P), np.float32), mp=has.astype(np.float32))


def run(recs: list, variant: str) -> pd.DataFrame:
    import jax
    import optax
    import hinigram_resonet as R
    import pickle
    R.CFG["pool"] = True
    rows = []
    for seed in (0, 1):
        for fold in range(3):
            with open(os.path.join(HERE, "mlruns", f"{variant}_f{fold}_s{seed}_params.pkl"), "rb") as fh:   # our own saved weights
                d = pickle.load(fh)
            cal = json.load(open(os.path.join(HERE, "mlruns", f"{variant}_f{fold}_s{seed}_summary.json")))["calibration"]
            tau = cal["tau"] if cal["val_coverage"] > 0 else -np.inf
            arm, shifts = d["arm"], d["shifts"]
            fwd = jax.jit(lambda p, s, x, prof: R.forward(p, s, x, prof, arm, shifts, False, jax.random.PRNGKey(7))[:3])
            labels = {k: ("train" if k in TUNED else "freeze") for k in d["params"]}
            opt = optax.multi_transform({"train": optax.adamw(LR, weight_decay=WD), "freeze": optax.set_to_zero()}, labels)

            @jax.jit
            def step(p, s, o, b):
                (l, _), g = jax.value_and_grad(R.loss_fn, has_aux=True)(p, s, b, arm, shifts, False, jax.random.PRNGKey(0))
                upd, o2 = opt.update(g, o, p)
                return optax.apply_updates(p, upd), o2, l

            for k, test in enumerate(recs):
                train = [r for j, r in enumerate(recs) if j != k]
                b = _batch(R, np.concatenate([r["P"] for r in train]), np.concatenate([r["rate"] for r in train]))
                p = d["params"]
                o = opt.init(p)
                for _ in range(STEPS):
                    p, o, _ = step(p, d["state"], o, b)
                tb = _batch(R, test["P"], test["rate"])
                for when, params in (("before", d["params"]), ("after", p)):
                    mu, ls, pl = (np.asarray(a) for a in fwd(params, d["state"], tb["x"], tb["prof"]))
                    rate, sd, pp = np.exp(mu), np.exp(ls), 1 / (1 + np.exp(-pl))
                    has = np.isfinite(test["rate"])
                    err = np.abs(rate - test["rate"])[has]
                    shown = ((pp > 0.5) & (sd <= tau))[has]
                    rows.append(dict(recording=test["name"], seed=seed, fold=fold, when=when, windows=int(has.sum()),
                                     within2_all=float(np.mean(err <= 2)), mae_all=float(np.mean(err)),
                                     shown=float(np.mean(shown)), useful=float(np.mean(shown & (err <= 2)))))
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["recording", "when"])[["windows", "within2_all", "mae_all", "shown", "useful"]].mean().reset_index()
    pooled = df.groupby(["when"])[["within2_all", "mae_all", "shown", "useful"]].mean().reset_index().assign(recording="all one-person recordings", windows=np.nan)
    out = pd.concat([g, pooled], ignore_index=True)
    for k in ("within2_all", "shown", "useful"):
        out[k] = (100 * out[k]).round(1)
    out["mae_all"] = out["mae_all"].round(2)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "hku":
        sys.exit(__doc__)
    folder = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "hku")
    recs = hku_recordings(folder)
    if len(recs) < 2:
        sys.exit("need at least two one-person recordings")
    variant = rd.load_rule()["rule"]["variant"]
    df = run(recs, variant)
    os.makedirs(rd.RESULTS, exist_ok=True)
    df.to_csv(os.path.join(rd.RESULTS, "finetune_hku_rows.csv"), index=False)
    s = summarise(df)
    s.to_csv(os.path.join(rd.RESULTS, "finetune_hku.csv"), index=False)
    print(s.to_string(index=False))
