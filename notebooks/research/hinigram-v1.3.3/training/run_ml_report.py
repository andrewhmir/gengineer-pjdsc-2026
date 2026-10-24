"""Compute every table and figure for the learned estimators from mldata/ and mlruns/ (no retraining)."""
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd

import hinigram_style as hs
import hinigram_ml_report as rep

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mlresults")
os.makedirs(OUT, exist_ok=True)
hs.use_style()
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)

test, w, arms = rep.collect(seed=seed)
w.to_csv(os.path.join(OUT, "window_table.csv.gz"), index=False)
rt = rep.rate_table(w, arms); rt.to_csv(os.path.join(OUT, "rate_table.csv"), index=False)
st = rep.screening_table(w, arms); st.to_csv(os.path.join(OUT, "screening_table.csv"), index=False)
nt = rep.null_test(arms, seed); nt.to_csv(os.path.join(OUT, "null_test.csv"), index=False)
ft = rep.fold_table(w, arms); ft.to_csv(os.path.join(OUT, "fold_table.csv"), index=False)
pairs = rep.main_pairs(seed)
labels = {f"{a} - {b}": rep.contrast_label(a, b) for a, b in pairs}
res, tab = rep.contrasts(w, pairs, "useful")
res2, _ = rep.contrasts(w, pairs, "off5")
for r, fn in ((res, "contrasts_useful.csv"), (res2, "contrasts_off5.csv")):
    out = r.copy(); out.insert(1, "label", out.contrast.map(labels))
    out["ci_low"], out["ci_high"] = out.ci.map(lambda c: c[0]), out.ci.map(lambda c: c[1])
    out.drop(columns="ci").to_csv(os.path.join(OUT, fn), index=False)
grid = np.linspace(0.05, 0.8, 16)
rc = pd.DataFrame({a: rep.me.risk_coverage(w[w.arm == a], grid) for a in ["dsp"] + arms}, index=np.round(grid, 3))
rc.to_csv(os.path.join(OUT, "risk_coverage.csv"))
cal = []
for a in arms:
    for f in range(3):
        j = json.load(open(os.path.join(rep.me.RUNS, f"{a}_f{f}_s{seed}_summary.json")))
        cal.append(dict(arm=a, fold=f, epochs=len(j["hist"]), best_val=min(h["val"] for h in j["hist"]), **j["calibration"]))
pd.DataFrame(cal).to_csv(os.path.join(OUT, "calibration.csv"), index=False)
variants = {b: rep.best_variant(b, seed) for b in ("lin_power", "shallow")}
json.dump(variants, open(os.path.join(OUT, "validation_choices.json"), "w"), indent=1)
comp = []                                      # what the training files contain, for the notebook when mldata/ is absent
for f in sorted(glob.glob(os.path.join(rep.hd.HERE, "mldata", "train", "*.npz"))):
    sp = json.loads(str(np.load(f)["spec"]))
    for L in sp["links"]:
        rates = [r for _, _, r in L["segments"] if r > 0]
        comp.append(dict(file=os.path.basename(f), profile=L["profile"], depth=L["depth"], rate_min=min(rates), rate_max=max(rates),
                         pause=any(r == 0 for _, _, r in L["segments"]), change=len(set(rates)) > 1))
pd.DataFrame(comp).to_csv(os.path.join(OUT, "training_composition.csv"), index=False)

print(rt.round(3).to_string()); print(st.round(3).to_string()); print(nt.to_string()); print(ft.round(3).to_string())
print(res.round(4).to_string()); print(res2.round(4).to_string()); print(rc.round(3).to_string())
print(pd.DataFrame(cal).round(3).to_string()); print("validation-chosen variants:", variants)
leak = rep.surrogate_leak_demo(); leak.to_csv(os.path.join(OUT, "surrogate_leak_demo.csv"), index=False); print(leak.to_string())

seeds = [s for s in (0, 1) if rep.trained_arms(s)]
if len(seeds) > 1:
    sr, sc = rep.seed_tables(seeds)
if len(seeds) > 1 and len(sc):
    sc.insert(2, "label", sc.contrast.map(lambda c: rep.contrast_label(*c.split(" - "))))
    sc["ci_low"], sc["ci_high"] = sc.ci.map(lambda c: c[0]), sc.ci.map(lambda c: c[1])
    sc = sc.drop(columns="ci")
    sr.to_csv(os.path.join(OUT, "seed_rate_table.csv"), index=False); sc.to_csv(os.path.join(OUT, "seed_contrasts.csv"), index=False)
    print(sr.round(4).to_string()); print(sc.round(4).to_string())

rc_arms = [a for a in [variants["shallow"], "lin_power", "lin_power-p0", "lin_surrogate", "lin_randphase", "lin_sync"] if a in arms]
for fig, fn in ((rep.fig_preprocessing(), "M1_preprocessing.png"),
                (rep.fig_training([a for a in ["shallow", "lin_power", "lin_surrogate", "lin_randphase", "lin_sync"] if a in arms]), "M2_training.png"),
                (rep.fig_oscillators("lin_sync", seed), "M3_oscillators.png"),
                (rep.fig_risk_coverage(w, rc_arms), "M4_risk_coverage.png")):
    fig.savefig(os.path.join(OUT, fn), dpi=160)
rep.fig_contrasts(res, labels).savefig(os.path.join(OUT, "M5_contrasts.png"), dpi=160)
print("saved to", OUT)
