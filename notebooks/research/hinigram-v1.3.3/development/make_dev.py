"""Extra development files for the v1.3.2 recency check (seeds 5 and 6; never used for reporting)."""
import os, sys, time
sys.path.insert(0, os.path.abspath("."))
import hinigram_live as hl
from semi_gen import MACS, SRC
DEPTHS = [0.06, 0.035, 0.02]
DEV = {
    "dev_child_pause": ([(0, 118, 30.0), (118, 143, 0), (143, 180, 30.0)], "child_1_5y"),
    "dev_adult_pause_early": ([(0, 36, 18.0), (36, 54, 0), (54, 180, 18.0)], "adult"),
    "dev_infant_50": ([(0, 180, 50.0)], "infant_2_12m"),
    "dev_adult_6": ([(0, 180, 6.5)], "adult"),
    "dev_adult_pause_late": ([(0, 122, 13.0), (122, 138, 0), (138, 180, 13.0)], "adult"),
}
def scen(name, seed):
    segs, _ = DEV[name]
    return {m: hl.BreathingScenario(segs, depth=d, phase_depth=d, seed=seed * 10 + i, name=name) for i, (m, d) in enumerate(zip(MACS, DEPTHS))}
if __name__ == "__main__":
    t = time.time()
    for seed in (5, 6):
        for name in DEV:
            dst = f"dev132/{name}_s{seed}.csv"
            if not os.path.exists(dst):
                hl.inject_breathing(SRC, dst, scen(name, seed))
    print(f"done in {time.time() - t:.0f} s")
