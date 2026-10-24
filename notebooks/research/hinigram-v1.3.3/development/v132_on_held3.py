"""Diagnostic only: frozen v1.3.2 on held-out set 3 files (already seen while diagnosing v1.3.1, so not an
independent test). Separates version effects from seed effects when comparing set 3 (v1.3.1) with set 4 (v1.3.2)."""
import json, os, sys
sys.path.insert(0, os.path.abspath("."))      # run from the bundle folder
import numpy as np, pandas as pd
import hinigram_live as hl, hinigram_eval as he
from validate_heldout4 import HELD   # same eleven scenarios as set 3
from validate_heldout import truth_status, WIN, MACS, SRC, DEPTHS
rows3 = pd.DataFrame(json.load(open("heldout3_rows.json")))
out = []
os.makedirs("semi_heldout3", exist_ok=True)
for seed in (31, 32):
    for name, (segs, prof) in HELD.items():
        path = f"semi_heldout3/{name}_s{seed}.csv"
        if not os.path.exists(path):   # the injection is seeded, so this recreates set 3's files exactly
            scs = {m: hl.BreathingScenario(segs, depth=d, phase_depth=d, seed=seed * 10 + i, name=name) for i, (m, d) in enumerate(zip(MACS, DEPTHS))}
            hl.inject_breathing(SRC, path, scs)
        S = hl.load_csi_session(path)
        tr = hl.analyze_session(S, hl.RRConfig(profile=prof))
        for mac in MACS:
            T = tr[mac]
            for i, te in enumerate(T.t):
                out.append(dict(scenario=name, seed=seed, mac=mac, t=float(te), new_bpm=float(T.bpm[i]), new_reliable=bool(T.reliable[i]),
                                new_status=T.status[i], new_reason=T.reason[i], new_pause_est=float(T.pause_est[i])))
v = pd.DataFrame(out)
key = ["scenario", "seed", "mac"]
r = rows3[rows3.scenario != "raw_sample_null"].copy()
r = r.sort_values(key + ["t"]).reset_index(drop=True); v = v.sort_values(key + ["t"]).reset_index(drop=True)
assert len(r) == len(v) and np.allclose(r.t.values, v.t.values)
for c in ("new_bpm", "new_reliable", "new_status", "new_reason", "new_pause_est"):
    r[c] = v[c].values
rows = r.to_dict("records") + rows3[rows3.scenario == "raw_sample_null"].to_dict("records")   # null rows: v1.3.1's (v1.3.2 gives the same single reading)
json.dump(rows, open("v132_on_heldout3_rows.json", "w"))
m = he.compute(rows)
print("reassurance", m["pause_reassurance"], "big", len(m["big_errors"]), "answered", m["answered_accuracy"], "ba", np.round(m["ba"]["loa"], 2))
print(he.pause_summary(m["pauses"]).to_string()); print("false pause", m["false_pause"])
print(m["per_depth"].round(3).to_string())
