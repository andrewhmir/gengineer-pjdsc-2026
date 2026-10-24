"""
hinigram_fallback.py: v1.3.2 first, the learned estimator only where v1.3.2 abstains
====================================================================================
The next step Part 2 of the notebook proposed for the learned estimator: keep v1.3.2's reading wherever it shows one,
and use ResoNet (sync readout) only where v1.3.2 abstains and the model passes a stricter threshold. Defined on
validation data, frozen, then tested once on a fresh held-out set.

1. ``choose``  Validation files only (seeds 2000-2029). For each trained model (two seeds x three folds; each fold's
              model is scored on the two sensors it trained on, as its own calibration was), the threshold on the
              model's predicted SD is the largest one for which the windows it adds are within +/-2 per minute at least
              97% of the time (the model's own operating point asked for 95%), and at most 1% of the windows with no
              breathing in their newest 6 s are given a rate. The model is never used while v1.3.2 sees movement or
              its recency check says breathing has faded, nor when the model's own breathing-present probability is
              0.5 or less. The 40- and 80-epoch schedules are compared on validation too, and the one adding more
              correct readings there is used.
2. ``freeze``  Writes results/fallback_rule.json: every threshold, the conditions and the validation numbers, with the
              SHA-256 of the rule. Nothing after this point changes it.
3. ``test``    Builds held-out set 6 (seeds 61 and 62, the eleven held-out scenarios, depths rotated over the sensors
              as in set 5), which no model and no choice has seen, and scores v1.3.2 alone, the model alone and the
              fallback through the same screening state machine. Refuses to run twice for the same rule.

    python hinigram_fallback.py choose      (validation only; prints and stores the candidate rule)
    python hinigram_fallback.py freeze
    python hinigram_fallback.py test        (builds set 6 on first use, about 2 minutes on 4 cores)
"""
from __future__ import annotations

import datetime
import glob
import hashlib
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

import hinigram_dataset as hd
import hinigram_ml_eval as ev

HERE = hd.HERE
RESULTS = os.path.join(HERE, "results")
RULE_PATH = os.path.join(RESULTS, "fallback_rule.json")
CAND_PATH = os.path.join(RESULTS, "fallback_candidate.json")
TEST_PATH = os.path.join(RESULTS, "fallback_set6.json")
TARGET, ABSENT_MAX, MIN_ACCEPTED = 0.97, 0.01, 30
VARIANTS = ["lin_sync", "lin_sync-e80"]
SEEDS = [0, 1]


def _model(variant, fold, seed):
    import hinigram_resonet as R
    with open(os.path.join(ev.RUNS, f"{variant}_f{fold}_s{seed}_params.pkl"), "rb") as fh:   # written by hinigram_resonet.run
        d = pickle.load(fh)
    R.CFG["pool"] = True
    return R, d


def predict_split(variant, fold, seed, kind, links):
    """Model outputs for every window of the given split and links, keyed (file index, link)."""
    R, d = _model(variant, fold, seed)
    sp = R.Split(R.split_files(kind), links, every=1)
    pr = R.predict(d["params"], d["state"], d["arm"], d["shifts"], sp)
    out = {}
    for fi in np.unique(sp.meta["file"]):
        for li in links:
            m = (sp.meta["file"] == fi) & (sp.meta["link"] == li)
            order = np.argsort(sp.meta["k"][m])
            out[(int(fi), int(li))] = {k: v[m][order] for k, v in pr.items()}
    return out


def eligible(L, pr):
    """Windows where the model may add a reading: v1.3.2 shows none, no movement, recency not low, model says breathing."""
    d = L["dsp"]
    return (~d["reliable"].astype(bool)) & (~d["motion"].astype(bool)) & (~d["recent_low"].astype(bool)) & (pr["p_present"] > 0.5)


def choose_threshold(data, preds):
    """Largest SD threshold meeting the accuracy and no-breathing limits on these validation windows."""
    el, sd, ok, has, absent = [], [], [], [], []
    for (fi, li), pr in preds.items():
        L = data[fi]["links"][li]
        e = eligible(L, pr)
        el.append(e); sd.append(pr["sd"]); has.append(np.isfinite(L["rate"]))
        ok.append(np.abs(pr["rate"] - np.nan_to_num(L["rate"], nan=-99)) <= 2.0)
        absent.append(L["present"] == 0)
    el, sd, ok, has, absent = map(np.concatenate, (el, sd, ok, has, absent))
    abstain_with_truth = (has & ~np.concatenate([data[fi]["links"][li]["dsp"]["reliable"].astype(bool) for (fi, li) in preds])).sum()
    best = dict(tau=None, added=0.0, within=None, absent_rate=0.0, accepted=0)      # None: no threshold qualifies, nothing is added
    for tau in np.unique(np.quantile(sd[el], np.linspace(0.005, 1.0, 400))) if el.any() else []:
        acc = el & (sd <= tau)
        a_truth = acc & has
        if a_truth.sum() < MIN_ACCEPTED:
            continue
        within = float(ok[a_truth].mean())
        absent_rate = float(acc[absent].mean()) if absent.any() else 0.0
        if within >= TARGET and absent_rate <= ABSENT_MAX:
            added = float((a_truth & ok).sum() / max(abstain_with_truth, 1))
            if added > best["added"]:
                best = dict(tau=float(tau), added=added, within=within, absent_rate=absent_rate, accepted=int(a_truth.sum()))
    return best


def choose():
    val = [hd.load_npz(f) for f in sorted(glob.glob(os.path.join(HERE, "mldata", "val", "*.npz")))]
    out = {}
    for variant in VARIANTS:
        if not all(os.path.exists(os.path.join(ev.RUNS, f"{variant}_f{f}_s{s}_params.pkl")) for f in range(3) for s in SEEDS):
            print(f"{variant}: not every fold and seed is trained; skipped")
            continue
        out[variant] = {}
        for seed in SEEDS:
            for fold in range(3):
                links = [l for l in range(3) if l != fold]
                th = choose_threshold(val, predict_split(variant, fold, seed, "val", links))
                out[variant][f"s{seed}_f{fold}"] = th
                print(f"{variant} seed {seed} fold {fold}: tau {th['tau']:.4f}, adds a correct reading in {100 * th['added']:.1f}% of the windows "
                      f"v1.3.2 leaves unread, {100 * th['within']:.1f}% within 2, no-breathing windows given a rate {100 * th['absent_rate']:.2f}%", flush=True)
        out[variant]["mean_added"] = float(np.mean([v["added"] for k, v in out[variant].items() if k.startswith("s")]))
    # the 80-epoch schedule replaces the 40-epoch one only if it adds more in at least 4 of the 6 (seed, fold) models
    pick = "lin_sync"
    if "lin_sync-e80" in out and "lin_sync" in out:
        keys = [k for k in out["lin_sync"] if k.startswith("s")]
        wins = sum(out["lin_sync-e80"][k]["added"] > out["lin_sync"][k]["added"] for k in keys)
        out["e80_wins"] = f"{wins}/{len(keys)}"
        if wins >= 4:
            pick = "lin_sync-e80"
    elif out:
        pick = next(iter(out))
    cand = dict(variant=pick, target_within2=TARGET, absent_max=ABSENT_MAX, min_accepted=MIN_ACCEPTED, validation=out,
                conditions=["v1.3.2 shows no rate in the window", "v1.3.2 sees no movement", "v1.3.2's recency check is not low",
                            "the model's breathing-present probability is above 0.5", "the model's predicted SD is at most tau (per fold and seed)"],
                state_machine="v1.3.2's: the fallback replaces only the rate and the reliable flag where it adds a reading",
                limits="Set 6 uses the same eleven scenarios, depths, background recording and movement times as set 5, with new "
                       "random draws (rate variability, subcarrier patterns). It is fresh for this rule, not a new room or new people.")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(cand, open(CAND_PATH, "w"), indent=1)
    print(f"chosen on validation: {pick} (mean share of v1.3.2's unread windows given a correct reading: "
          + ", ".join(f"{v} {100 * out[v]['mean_added']:.1f}%" for v in VARIANTS if v in out) + f"; 80 epochs better in {out.get('e80_wins', '-')} models)")
    return cand


def freeze():
    if os.path.exists(RULE_PATH):
        sys.exit(f"{RULE_PATH} exists: the rule is already frozen")
    cand = json.load(open(CAND_PATH))
    body = json.dumps(cand, sort_keys=True)
    rule = dict(rule=cand, sha256=hashlib.sha256(body.encode()).hexdigest(),
                frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                note="Frozen before held-out set 6 existed. test() checks this hash before it scores anything.")
    json.dump(rule, open(RULE_PATH, "x"), indent=1)
    print("frozen:", rule["sha256"])
    return rule


def load_rule():
    rule = json.load(open(RULE_PATH))
    if hashlib.sha256(json.dumps(rule["rule"], sort_keys=True).encode()).hexdigest() != rule["sha256"]:
        sys.exit("the frozen rule was changed after freezing")
    return rule


def build_set6():
    import subprocess
    if len(glob.glob(os.path.join(HERE, "mldata", "test6", "*.npz"))) >= 66:
        return
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", HINIGRAM_WORKERS=os.environ.get("HINIGRAM_WORKERS", "4"))
    subprocess.run([sys.executable, os.path.join(HERE, "hinigram_dataset.py"), "test6"], check=True, env=env, cwd=HERE)


def tables(kind, rule):
    """Window tables for v1.3.2 alone, the model alone (its own 95% operating point) and the fallback."""
    test = ev.load_test(kind)
    r = rule["rule"]
    variant = r["variant"]
    # v1.3.2 through the same re-screening as the fallback, so screening differences come only from the readings added
    dsp_rs = {}
    for fi, d in enumerate(test):
        for li, L in enumerate(d["links"]):
            dd = L["dsp"]
            dsp_rs[(fi, li)] = dict(rate=dd["bpm"], sd=1.0 - dd["quality"], p=np.ones(len(dd["bpm"])), shown=dd["reliable"].astype(bool))
    arms = [("dsp", 0, None), ("dsp_rescreened", 0, dsp_rs)]
    for seed in SEEDS:
        model, fb = {}, {}
        for fold in range(3):
            cal = json.load(open(os.path.join(ev.RUNS, f"{variant}_f{fold}_s{seed}_summary.json")))["calibration"]
            tau_m = cal["tau"] if cal["val_coverage"] > 0 else -np.inf
            tau_f = r["validation"][variant][f"s{seed}_f{fold}"]["tau"]
            tau_f = -np.inf if tau_f is None else tau_f
            for key, pr in predict_split(variant, fold, seed, kind, [fold]).items():
                L = test[key[0]]["links"][key[1]]
                d = L["dsp"]
                model[key] = dict(rate=pr["rate"], sd=pr["sd"], p=pr["p_present"], shown=(pr["p_present"] > 0.5) & (pr["sd"] <= tau_m))
                add = eligible(L, pr) & (pr["sd"] <= tau_f)
                rel = d["reliable"].astype(bool) | add
                fb[key] = dict(rate=np.where(d["reliable"].astype(bool), d["bpm"], pr["rate"]), sd=np.where(d["reliable"].astype(bool), 0.0, pr["sd"]),
                               p=pr["p_present"], shown=rel, added=add)
        arms += [("model", seed, model), ("fallback", seed, fb)]
    w = ev.window_table(test, arms)
    return w


def summarise(w):
    rows = []
    # rates come from the readings; screening rows compare the fallback with dsp_rescreened (same state-machine call)
    for (arm, seed), d in w.groupby(["arm", "seed"]):
        rm, sm = ev.rate_metrics(d), ev.screening_metrics(d)
        rows.append(dict(method=arm, seed=seed, **rm, **sm))
    tab = pd.DataFrame(rows)
    useful = ev.per_run(w, "useful")
    off5 = ev.per_run(w, "off5")
    contrasts = [ev.paired(useful, "fallback", "dsp"), ev.paired(useful, "fallback", "model"), ev.paired(off5, "fallback", "dsp")]
    adj = ev.holm([c["w_p"] for c in contrasts])          # one family, Wilcoxon p-values (as hinigram_ml_report.contrasts)
    for c, a in zip(contrasts, adj):
        c["holm_p"] = float(a)
        c["metric"] = "off by more than 5" if c is contrasts[2] else "useful readings"
    return tab, pd.DataFrame(contrasts)


def test(force=False):
    rule = load_rule()
    if os.path.exists(TEST_PATH) and not force:
        prev = json.load(open(TEST_PATH))
        if prev.get("rule_sha256") == rule["sha256"]:
            sys.exit(f"set 6 was already scored with this rule ({TEST_PATH}); held-out sets are scored once")
    build_set6()
    w = tables("test6", rule)
    tab, con = summarise(w)
    w.to_csv(os.path.join(RESULTS, "fallback_window_table.csv.gz"), index=False)
    tab.to_csv(os.path.join(RESULTS, "fallback_set6_rates.csv"), index=False)
    con.to_csv(os.path.join(RESULTS, "fallback_set6_contrasts.csv"), index=False)
    json.dump(dict(rule_sha256=rule["sha256"], scored_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                   rates=tab.to_dict(orient="records"), contrasts=con.to_dict(orient="records")), open(TEST_PATH, "w"), indent=1, default=str)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(tab.round(3).to_string(index=False))
        print(con.to_string(index=False))
    return tab, con


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "choose"
    {"choose": choose, "freeze": freeze, "test": test}[step]()
