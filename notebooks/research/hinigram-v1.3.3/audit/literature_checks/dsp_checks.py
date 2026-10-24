import numpy as np, scipy.signal as sig, math

np.set_printoptions(precision=4, suppress=True)

def project_hilbert_taps(n_taps=31):
    # exact copy of the project's causal_hilbert_transform taps (cell_06.py lines 6-11)
    half = n_taps // 2
    n = np.arange(-half, half + 1)
    h = np.zeros(n_taps)
    odd = (n % 2 != 0)
    h[odd] = 2.0 / (np.pi * n[odd])
    h *= np.hamming(n_taps)
    return h

print("=== A. 31-tap Hamming Type-III Hilbert FIR (project taps) ===")
fs = 100.0
h = project_hilbert_taps(31)
print("antisymmetric:", np.allclose(h, -h[::-1]), " sum(h)=", h.sum())
freqs = np.array([0.05, 0.10, 0.12, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 1.0, 2.0, 5.0, 10.0, 25.0, 40.0, 45.0, 49.0])
w, H = sig.freqz(h, worN=freqs, fs=fs)
for f, g in zip(freqs, np.abs(H)):
    print(f"  f={f:6.2f} Hz  (norm f/fs={f/fs:.4f})  |H|={g:.4f}  ({20*np.log10(g):6.1f} dB)")
# passband: where |H| within 1 dB (0.891) and 0.1 dB of 1
fgrid = np.linspace(0.001, 49.999, 200000)
_, Hg = sig.freqz(h, worN=fgrid, fs=fs)
mag = np.abs(Hg)
for thr in [0.891, 0.977, 0.99]:
    idx = np.where(mag >= thr)[0]
    print(f"  |H|>={thr}: from {fgrid[idx[0]]:.2f} Hz to {fgrid[idx[-1]]:.2f} Hz")
print("  group delay (N-1)/2 =", (31-1)//2, "samples =", 15/fs, "s at fs=100")
# low-frequency slope check: |H| ~ 2*w*sum_{n>0} n*h_pos[n]
half = 15
hpos = h[half+1:]
slope = 2*np.sum(np.arange(1, half+1)*hpos)  # dH/dw at 0 (magnitude)
print("  small-w approximation |H|~ slope*w, slope=", slope, "-> at 0.25 Hz:", slope*2*np.pi*0.25/fs)

# Phase error of analytic signal built from delayed x + j*H{x} for a 0.25 Hz tone
for f0 in [0.12, 0.25, 0.6]:
    t = np.arange(0, 120, 1/fs)
    x = np.cos(2*np.pi*f0*t)
    yq = sig.lfilter(h, [1.0], x)
    xd = np.concatenate([np.zeros(15), x[:-15]])
    ph_est = np.arctan2(yq, xd)[3000:]
    ph_true = np.angle(np.exp(1j*(2*np.pi*f0*(t-0.15))))[3000:]
    err = np.angle(np.exp(1j*(ph_est - ph_true)))
    # what the project actually does if this filter were used: real part NOT delayed
    ph_nodelay = np.arctan2(yq, x)[3000:]
    err2 = np.angle(np.exp(1j*(ph_nodelay - np.angle(np.exp(1j*2*np.pi*f0*t))[3000:])))
    print(f"  tone {f0} Hz: max |phase error| with delayed I-branch = {np.degrees(np.max(np.abs(err))):.1f} deg; "
          f"w/o delaying I-branch = {np.degrees(np.max(np.abs(err2))):.1f} deg; envelope ripple max/min = {np.max(np.abs(xd[3000:]+1j*yq[3000:]))/np.min(np.abs(xd[3000:]+1j*yq[3000:])):.1f}")

print("\n=== A2. Required Hilbert FIR length for lower band edge f_L ===")
def hilbert_len_needed(fs, fL, tol=0.01, kind='hamming', nmax=6001):
    for N in range(11, nmax, 2):
        if kind == 'hamming':
            half = N//2; n = np.arange(-half, half+1); hh = np.zeros(N); o = n % 2 != 0
            hh[o] = 2/(np.pi*n[o]); hh *= np.hamming(N)
        else:
            try:
                hh = sig.remez(N, [fL, fs/2 - fL], [1], type='hilbert', fs=fs)
            except Exception:
                continue
        fg = np.linspace(fL, fs/2 - fL, 4000)
        _, HH = sig.freqz(hh, worN=fg, fs=fs)
        if np.max(np.abs(np.abs(HH) - 1)) <= tol:
            return N
    return None
for fs_ in [100.0, 30.0, 10.0, 5.0, 2.0]:
    for fL in [0.10, 0.12]:
        for kind in ['hamming', 'remez']:
            N = hilbert_len_needed(fs_, fL, tol=0.01, kind=kind, nmax=4001 if fs_ >= 30 else 2001)
            if N:
                print(f"  fs={fs_:5.1f} Hz fL={fL} Hz {kind:7s}: N={N:5d} taps, delay=(N-1)/2={ (N-1)//2 } samples = {(N-1)/2/fs_:.2f} s  (|H| within 1% on [fL, fs/2-fL])")
            else:
                print(f"  fs={fs_:5.1f} Hz fL={fL} Hz {kind:7s}: >limit")

print("\n=== B. 4th-order Butterworth bandpass 0.12-0.60 Hz group delay ===")
for fs_ in [100.0, 30.0, 28.5]:
    sos = sig.butter(4, [0.12, 0.60], btype='bandpass', fs=fs_, output='sos')
    b, a = sig.sos2tf(sos)
    print(f" fs={fs_}: total order={2*len(sos)} poles; sections={len(sos)}")
    for f0 in [0.12, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60]:
        # numerical group delay from phase derivative of sosfreqz
        df = 1e-4
        _, H1 = sig.sosfreqz(sos, worN=[f0-df, f0, f0+df], fs=fs_)
        ph = np.unwrap(np.angle(H1))
        gd = -(ph[2]-ph[0])/(2*2*np.pi*df)
        print(f"   f={f0:.2f} Hz: |H|={np.abs(H1[1]):.3f}, group delay={gd:.2f} s, phase={np.degrees(np.angle(H1[1])):7.1f} deg")
    # impulse response duration: time until |h| envelope stays below 1% of peak
    n = int(120*fs_)
    imp = np.zeros(n); imp[0] = 1
    hr = sig.sosfilt(sos, imp)
    env = np.abs(sig.hilbert(hr))
    pk = env.max()
    t99 = np.where(env > 0.01*pk)[0][-1]/fs_
    e = np.cumsum(hr**2); t_e99 = np.where(e >= 0.99*e[-1])[0][0]/fs_
    print(f"   impulse response: envelope >1% of peak until {t99:.1f} s; 99% energy by {t_e99:.1f} s; peak at {np.argmax(np.abs(hr))/fs_:.2f} s")
    # default padlen for sosfiltfilt
    ntaps = 2*len(sos)+1 - min((sos[:,2]==0).sum(), (sos[:,5]==0).sum())
    print(f"   scipy default sosfiltfilt padlen = 3*{ntaps} = {3*ntaps} samples = {3*ntaps/fs_:.2f} s; project uses padlen=min(24,T-2)= 24 samples = {24/fs_:.2f} s")

# edge error of sosfiltfilt(padlen=24) vs reference on a 6 s window
print("\n=== B2. sosfiltfilt edge error on 6-s window (fs=100) ===")
fs_ = 100.0
sos = sig.butter(4, [0.12, 0.60], btype='bandpass', fs=fs_, output='sos')
t_long = np.arange(0, 200, 1/fs_)
rng = np.random.default_rng(0)
errs = {"padlen24": [], "default": [], "gust_like_none": [], "causal_sosfilt_zi": []}
for trial in range(50):
    ph0 = rng.uniform(0, 2*np.pi)
    xlong = np.sin(2*np.pi*0.25*t_long + ph0) + 0.3*np.sin(2*np.pi*0.03*t_long + 1.0)  # breathing + slow drift
    ref_long = sig.sosfiltfilt(sos, xlong)   # long-record zero-phase reference
    i0 = 10000; w = 600
    xw = xlong[i0:i0+w]; refw = ref_long[i0:i0+w]
    xw0 = xw - xw.mean()
    y24 = sig.sosfiltfilt(sos, xw0, padlen=24)
    yd = sig.sosfiltfilt(sos, xw0)  # default padlen (odd extension)
    errs["padlen24"].append(np.sqrt(np.mean((y24-refw)**2))/np.std(refw))
    errs["default"].append(np.sqrt(np.mean((yd-refw)**2))/np.std(refw))
    zi = sig.sosfilt_zi(sos)*xw0[0]
    yc, _ = sig.sosfilt(sos, xw0, zi=zi)
    # causal reference = long-record causal output at same indices (steady state)
    refc = sig.sosfilt(sos, xlong)[i0:i0+w]
    errs["causal_sosfilt_zi"].append(np.sqrt(np.mean((yc-refc)**2))/np.std(refc))
for k, v in errs.items():
    if v:
        print(f"  {k:20s}: normalized RMS error over 6-s window = {np.mean(v):.2f} (median {np.median(v):.2f})")

print("\n=== C. Savitzky-Golay (window 15, polyorder 3) frequency response ===")
for fs_, wl in [(100.0, 15), (30.0, 15)]:
    c = sig.savgol_coeffs(wl, 3)
    fg = np.linspace(0.001, fs_/2, 20000)
    _, Hs = sig.freqz(c, worN=fg, fs=fs_)
    m = np.abs(Hs)
    f3 = fg[np.where(m < 1/np.sqrt(2))[0][0]]
    _, H06 = sig.freqz(c, worN=[0.6], fs=fs_)
    print(f"  fs={fs_}: -3 dB cutoff = {f3:.2f} Hz; |H(0.6 Hz)| = {np.abs(H06[0]):.6f}; centered => {wl//2} samples look-ahead = {wl//2/fs_*1000:.0f} ms")

print("\n=== D. Welch grid check (fs=30, nperseg=128) ===")
fsw = 30.0
print("  fs/nperseg =", fsw/128, " 5x =", 5*fsw/128, " 6x =", 6*fsw/128)
for T in [150, 300]:
    f_w, P_w = sig.welch(np.random.randn(T), fs=fsw, nperseg=min(T, 128))
    nseg = (T - 128)//64 + 1
    print(f"  T={T}: n freq bins={len(f_w)}, first bins={f_w[:4]}, segments={nseg}")
for ftone in [0.15, 0.22, 0.28, 0.32, 0.36, 0.45]:
    tt = np.arange(150)/fsw
    xx = np.sin(2*np.pi*ftone*tt + 0.3); xx -= xx.mean()
    f_w, P_w = sig.welch(xx, fs=fsw, nperseg=128)
    print(f"  pure tone {ftone:.2f} Hz, T=150 -> Welch peak at {f_w[np.argmax(P_w)]:.3f} Hz")

print("\n=== E. Linear damped resonator equivalents (mu=-0.25) ===")
mu = -0.25
print(f"  time constant 1/|mu| = {1/abs(mu):.1f} s; -3dB full bandwidth = 2|mu| rad/s = {2*abs(mu)/(2*np.pi):.4f} Hz; Q at 0.25 Hz = {2*np.pi*0.25/(2*abs(mu)):.2f}")
fr = np.linspace(0.15, 2.5, 12)
print("  bank freqs (Hz):", fr, " spacing", fr[1]-fr[0])
print("  transient remaining after 5 s (T=150 @30Hz): exp(mu*5)=", np.exp(mu*5), "; after 10 s:", np.exp(mu*10))

print("\n=== F. PLL linearization of project oscillator ===")
for mu_ in [0.5, 1.0]:
    for eps in [0.95, 2.2, 2.4]:
        K = 1.65; A = math.sqrt(2.0)  # analytic amplitude of unit-std sinusoid
        # steady radius r: r^3 - mu r - K A = 0 (locked, zero phase error)
        roots = np.roots([1, 0, -mu_, -K*A]); r = float(np.max(roots[np.isreal(roots)].real))
        Kp = K*A/r; Ki = eps*A
        wn = math.sqrt(Ki); zeta = Kp/(2*wn)
        BL = (wn/2)*(zeta + 1/(4*zeta))  # one-sided noise bandwidth in Hz (wn in rad/s)
        tsettle = 4/(zeta*wn) if zeta < 1 else float('nan')
        print(f"  mu={mu_}, eps={eps}: r*={r:.3f}, Kp=K|F|/r={Kp:.3f} rad/s, Ki=eps|F|={Ki:.3f} rad/s^2, "
              f"wn={wn:.3f} rad/s ({wn/(2*np.pi):.3f} Hz), zeta={zeta:.3f}, B_L={BL:.3f} Hz, 2% settling~4/(zeta wn)={tsettle:.1f} s")
