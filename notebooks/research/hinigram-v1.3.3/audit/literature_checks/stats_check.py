import math
try:
    from scipy.stats import binom, norm, t as tdist
    have_scipy = True
except Exception as e:
    have_scipy = False
    print("no scipy:", e)

def binom_sf_ge(k, n, p):
    # P(X >= k) exact
    return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))

def binoinv(q, n, p):
    # smallest x with CDF(x) >= q (MATLAB binoinv / scipy ppf convention)
    c = 0.0
    for x in range(n+1):
        c += math.comb(n, x) * p**x * (1-p)**(n-x)
        if c >= q - 1e-15:
            return x
    return n

print("=== Combrisson & Jerbi style chance thresholds, c=4 classes (p0=0.25), alpha=0.05 ===")
print("n | binoinv(0.95,n,.25) | thr=binoinv/n (must be EXCEEDED) | min #correct for p<=.05 | that acc | P(X>=binoinv) | P(X>=binoinv+1)")
for n in [20, 50, 80, 100, 132, 144, 160, 200, 300]:
    x = binoinv(0.95, n, 0.25)
    pa = binom_sf_ge(x, n, 0.25)
    pb = binom_sf_ge(x+1, n, 0.25)
    # min k with P(X>=k) <= 0.05
    k = next(k for k in range(n+1) if binom_sf_ge(k, n, 0.25) <= 0.05)
    print(f"{n} | {x} | {x/n:.4f} | {k} | {k/n:.4f} | {pa:.4f} | {pb:.4f}")
    if have_scipy:
        assert int(binom.ppf(0.95, n, 0.25)) == x

print()
print("=== Bonferroni-style alpha=0.01 for comparison ===")
for n in [80, 160, 300]:
    k = next(k for k in range(n+1) if binom_sf_ge(k, n, 0.25) <= 0.01)
    print(n, k, round(k/n,4))

print()
print("=== Bland-Altman: approx 95% CI half-width of each LoA = 1.96*sqrt(3/n)*s ===")
for n in [12, 20, 50, 100, 200]:
    print(n, round(1.96*math.sqrt(3/n),3), "x s")

print()
print("=== Hinigram reported LoA (-1.13, +0.75): implied bias and SD ===")
lo, hi = -1.13, 0.75
bias = (lo+hi)/2; sd = (hi-lo)/(2*1.96)
print("bias =", round(bias,3), "SD of differences =", round(sd,3))
for n in [20, 50, 1000]:
    hw = 1.96*math.sqrt(3/n)*sd
    print(f"n={n}: approx CI half-width per LoA = {hw:.3f} BPM -> lower LoA CI approx ({lo-hw:.2f}, {lo+hw:.2f}), upper LoA CI approx ({hi-hw:.2f}, {hi+hw:.2f})")
    if have_scipy:
        tq = tdist.ppf(0.975, n-1)
        se = math.sqrt(3*sd**2/n)
        print(f"   t-based (Bland-Altman 1986): +/- {tq*se:.3f}")
print("y-limit +/-0.6 BPM hides lower LoA by", round(abs(lo)-0.6,2), "and upper LoA by", round(hi-0.6,2))

print()
print("=== McNemar exact example: discordant counts ===")
def mcnemar_exact(b, c):
    n = b + c
    k = min(b, c)
    p = 2*sum(math.comb(n, i) for i in range(0, k+1)) / 2**n
    return min(1.0, p)
for b, c in [(12, 5), (10, 4), (20, 10), (8, 2)]:
    chi = (abs(b-c)-1)**2/(b+c)
    print(f"b={b}, c={c}: exact p={mcnemar_exact(b,c):.4f}; chi2_cc={chi:.3f}")

print()
print("=== Standard error of accuracy for small test sets (p=0.85) ===")
for n in [80, 132, 300]:
    se = math.sqrt(0.85*0.15/n)
    print(n, "SE=", round(se,4), "approx 95% CI half-width=", round(1.96*se,3))

print()
print("=== FIR linear-phase group delay examples ===")
for taps, fs in [(101, 100), (255, 50), (501, 100)]:
    gd = (taps-1)/2
    print(f"{taps} taps @ {fs} Hz: group delay {gd} samples = {gd/fs:.3f} s")
print("Window delay: a 30 s analysis window at hop 1 s -> first estimate after 30 s; estimate centred ~15 s in the past")
