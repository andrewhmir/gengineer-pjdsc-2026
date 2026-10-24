"""Arithmetic checks for derived numbers used in the Hinigram audit report."""
import numpy as np

c = 299792458.0

# 1. Sample-rate mismatch (V1.2 assumes fs = 100 Hz)
per_node = np.array([28.45, 28.87])
agg = 3 * per_node
print("aggregate Hz range:", agg, "mid", 3 * 28.66)
for fs_true, label in [(28.66, "per-node"), (3 * 28.66, "pooled 3 nodes")]:
    k = 100.0 / fs_true
    print(f"{label}: scale {k:.3f}; bandpass true Hz {0.12/k:.3f}-{0.60/k:.3f}"
          f" = {60*0.12/k:.1f}-{60*0.60/k:.1f} bpm; 600-packet window spans {600/fs_true:.2f} s")

# 2. Motion contamination of sliding windows
T = 173.0
eps = [(0, 17), (63, 68), (100, 107)]
print("motion seconds", sum(b - a for a, b in eps), "fraction", sum(b - a for a, b in eps) / T)
for W in (4, 6, 20, 30):
    ends = np.arange(W, T + 1e-9, 0.01)
    bad = np.zeros_like(ends, dtype=bool)
    for a, b in eps:
        bad |= (ends - W < b) & (ends > a)
    print(f"W={W:>2}s: contaminated window positions {bad.mean()*100:.1f}%")

# 3. AGC telegraph noise in band 0.12-0.60 Hz at fs 28.66 (symmetric two-level Markov switch)
fs = 28.66
for p in (0.35, 0.47):
    r = 1 - 2 * p
    f = np.linspace(0.12, 0.60, 2001)
    w = 2 * np.pi * f / fs
    S = (1 - r**2) / (1 - 2 * r * np.cos(w) + r**2)
    frac = 2 * np.trapezoid(S, f) / fs
    for step_db in (3, 9):
        hi = 10 ** (step_db / 20)
        rel_std = (hi - 1) / 2 / ((hi + 1) / 2)
        print(f"p={p}: in-band variance fraction {frac*100:.2f}%; step {step_db} dB ->"
              f" telegraph std {rel_std*100:.1f}% of mean, in-band std {rel_std*np.sqrt(frac)*100:.1f}%")
print("switches per second per node:", 28.45 * 0.35, 28.87 * 0.47)

# 4. Breathing retention of a cross-subcarrier ratio: 2|sin(pi df dtau)|
def keep(excess_m, df_hz):
    return 2 * abs(np.sin(np.pi * df_hz * excess_m / c))
for ex in (0.127, 0.5, 1.0, 3.0):
    print(f"excess {ex} m: centre ref (28 bins, 8.75 MHz) {keep(ex, 8.75e6):.4f};"
          f" edge ref (52 bins, 16.25 MHz) {keep(ex, 16.25e6):.4f}")

# 5. Fresnel: zone width and Gaussian model change per zone
lam = c / 2.437e9
print("lambda cm", lam * 100, "half-lambda cm", lam / 2 * 100, "zones in 1.15 m", 1.15 / (lam / 2))
e = np.linspace(0, 3, 300001)
G = np.exp(-(e / 1.15) ** 2)
dz = lam / 2
Gs = np.exp(-((e + dz) / 1.15) ** 2)
print("max absolute change of Gaussian across one zone (fraction of peak):", np.max(G - Gs))
e0 = 0.127
print("relative change across zone starting at 12.7 cm:",
      1 - np.exp(-((e0 + dz) / 1.15) ** 2) / np.exp(-(e0 / 1.15) ** 2))

# 6. Host-clock jitter vs packet interval and rate span
sd = 0.133
print("packet interval ms", 1000 / 28.66, "jitter in packet intervals", sd * 28.66)
for span in (3.5, 30.0):
    rel = np.sqrt(2) * sd / span
    print(f"span {span}s: endpoint-timing rate error ~{rel*100:.1f}% -> {rel*15:.2f} bpm at 15 bpm")

# 7. UART budget: ASCII line vs 136-byte binary frame at 921600 baud (10 bits/byte)
Bps = 921600 / 10
print("bytes/s", Bps, "ASCII lines/s (600-700 chars)", Bps / 700, Bps / 600, "binary 136B frames/s", Bps / 136)

# 8. Timestamp wrap
print("2^32 us wrap minutes:", 2**32 / 1e6 / 60)
