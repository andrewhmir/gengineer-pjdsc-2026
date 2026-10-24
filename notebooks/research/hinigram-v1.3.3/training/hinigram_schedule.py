"""
hinigram_schedule.py: the paper's training schedule (80 epochs, patience 15) against the 40-epoch sync arm, on set 5
==================================================================================================================
Writes the two tables of Part 2, Section 7 from the saved predictions of `lin_sync` and `lin_sync-e80` (both seeds,
three folds each) and v1.3.2, all through the same state machine (hinigram_ml_eval):

    results/schedule_e80_set5.csv            rates and screening per method and seed
    results/schedule_e80_set5_contrasts.csv  useful readings paired over runs: e80 against 40 epochs, and against v1.3.2
                                             (bootstrap 95% CI, Wilcoxon p, Holm over the two)

It also prints each run's validation coverage at the 95%-within-±2 operating point. Train the runs first:
    python ml_driver.py lin_sync-e80 0,1 "--epochs 80 --patience 15"
then, from training/ (set 5 must be in mldata/: python hinigram_dataset.py all):
    python hinigram_schedule.py
Set 5 had already been used for the original comparison, so this is a second look at it, not a fresh test.
"""
import json
import os

import numpy as np
import pandas as pd

import hinigram_ml_eval as ev

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    test = ev.load_test("test5")
    rows, arms = [], [("dsp", 0, None)]
    for arm in ("lin_sync", "lin_sync-e80"):
        for seed in (0, 1):
            arms.append((arm, seed, ev.model_predictions(arm, seed, test)))
    w = ev.window_table(test, arms)
    for (arm, seed), d in w.groupby(["arm", "seed"]):
        rm, sm = ev.rate_metrics(d), ev.screening_metrics(d)
        rows.append(dict(method=arm, seed=seed, shown=rm["shown"], within2=rm["within2"], useful=rm["useful"], off5=rm["off5"],
                         answered=sm["answered"], correct=sm["answered_correct"], pause_no_concern=sm["pause_no_concern"]))
    tab = pd.DataFrame(rows)
    print(tab.round(3).to_string(index=False))
    u = ev.per_run(w, "useful")
    res = [ev.paired(u, "lin_sync-e80", "lin_sync"), ev.paired(u, "lin_sync-e80", "dsp")]
    adj = ev.holm([r["w_p"] for r in res])
    for r, a in zip(res, adj):
        print(r["contrast"], f"mean {100 * r['mean']:+.1f} points, 95% CI {100 * r['ci'][0]:+.1f} to {100 * r['ci'][1]:+.1f}, wins {r['wins']}, Holm p {a:.2g}")
    out = os.path.join(HERE, "results")
    tab.to_csv(os.path.join(out, "schedule_e80_set5.csv"), index=False)
    pd.DataFrame(res).assign(holm_p=adj).to_csv(os.path.join(out, "schedule_e80_set5_contrasts.csv"), index=False)
    for arm in ("lin_sync", "lin_sync-e80"):
        cov = [json.load(open(os.path.join(HERE, "mlruns", f"{arm}_f{f}_s{s}_summary.json")))["calibration"]["val_coverage"]
               for s in (0, 1) for f in range(3)]
        print(f"validation coverage at 95% within ±2, {arm}: mean {100 * np.mean(cov):.1f}% ({', '.join(f'{100 * c:.0f}' for c in cov)})")


if __name__ == "__main__":
    main()
