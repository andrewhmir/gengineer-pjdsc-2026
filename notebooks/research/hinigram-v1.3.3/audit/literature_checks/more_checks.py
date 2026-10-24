import numpy as np, scipy.signal as sig, math

fs = 100.0
sos = sig.butter(4, [0.12, 0.60], btype='bandpass', fs=fs, output='sos')
imp = np.zeros(int(200*fs)); imp[0] = 1
hr = sig.sosfilt(sos, imp); a = np.abs(hr)
print("Impulse response of 0.12-0.60 Hz BPF: |h| last exceeds 1%% of peak at %.1f s; 0.1%% at %.1f s" %
      (np.where(a > 0.01*a.max())[0][-1]/fs, np.where(a > 0.001*a.max())[0][-1]/fs))
z, p, k = sig.butter(4, [0.12, 0.60], btype='bandpass', fs=fs, output='zpk')
pd_ = np.abs(p); tau = -1/(fs*np.log(pd_))
print("  pole radii time constants (s):", np.round(np.sort(tau)[::-1], 2))

# Edge error on 6-s windows, pure 0.25 Hz tone (passband gain 1, zero phase for filtfilt)
print("\nsosfiltfilt(padlen=24) on a 6-s window of a pure 0.25 Hz tone (ideal output = tone itself):")
rng = np.random.default_rng(1)
e_edge, e_mid, e_all = [], [], []
for _ in range(200):
    n = 600; tt = np.arange(n)/fs; ph = rng.uniform(0, 2*np.pi)
    x = np.sin(2*np.pi*0.25*tt + ph)
    y = sig.sosfiltfilt(sos, x - x.mean(), padlen=24)
    ideal = x - 0  # tone, gain ~1.000 at 0.25 Hz and zero phase
    err = y - ideal
    e_edge.append(np.sqrt(np.mean(np.r_[err[:100], err[-100:]]**2)))
    e_mid.append(np.sqrt(np.mean(err[250:350]**2)))
    e_all.append(np.sqrt(np.mean(err**2))/np.std(ideal))
print(f"  RMS error first/last 1 s = {np.mean(e_edge):.3f}; middle 1 s = {np.mean(e_mid):.3f} (tone amplitude 1); whole-window normalized RMS error = {np.mean(e_all):.3f}")
# compare with 'gust' (filtfilt with b,a) at fs=30
fs30 = 30.0; b, a_ = sig.butter(4, [0.12, 0.60], btype='bandpass', fs=fs30)
sos30 = sig.butter(4, [0.12, 0.60], btype='bandpass', fs=fs30, output='sos')
e_g, e_p = [], []
for _ in range(200):
    n = 180; tt = np.arange(n)/fs30; x = np.sin(2*np.pi*0.25*tt + rng.uniform(0, 2*np.pi))
    yg = sig.filtfilt(b, a_, x, method='gust'); yp = sig.sosfiltfilt(sos30, x, padlen=24)
    e_g.append(np.sqrt(np.mean((yg-x)**2))); e_p.append(np.sqrt(np.mean((yp-x)**2)))
print(f"  fs=30, 6-s window: normalized RMS err sosfiltfilt(padlen=24)={np.mean(e_p)/np.sqrt(0.5):.3f}; filtfilt(method='gust')={np.mean(e_g)/np.sqrt(0.5):.3f}")

# ---- Oscillator-bank regime check: copy of project data generator and bank (cell_02.py, cell_08.py) ----
def csi_bench_power_normalize(H_amp):
    power = np.abs(H_amp)**2; return (power / (np.sum(power, axis=-2, keepdims=True) + 1e-8)).astype(np.float32)
def generate(n_train=160, n_test=80, n_sub=56, T=150, fs=30.0, seed=42):
    rng = np.random.RandomState(seed); n_total = n_train + n_test
    X = np.zeros((n_total, n_sub, T), np.float32); y = np.zeros(n_total, np.int64)
    t = np.arange(T, dtype=np.float32)/fs; s = np.arange(n_sub, dtype=np.float32)
    for i in range(n_total):
        c = i % 4; y[i] = c; base = 10.0 + 1.5*np.cos(2*np.pi*s/n_sub)[:, None]
        if c == 0:
            f0 = rng.uniform(0.22, 0.32); ph0 = rng.uniform(0, 2*np.pi); mod = 2.0*np.sin(2*np.pi*s/28.0)[:, None]*np.sin(2*np.pi*f0*t[None, :]+ph0)
        elif c == 1:
            f0 = rng.uniform(0.44, 0.58); ph0 = rng.uniform(0, 2*np.pi); mod = 1.9*np.sin(2*np.pi*f0*t[None, :]+ph0+(2*np.pi*s/n_sub)[:, None])
        elif c == 2:
            f0 = rng.uniform(0.05, 0.08); mod = 0.12*np.sin(2*np.pi*f0*t[None, :])*np.ones((n_sub, 1))
        else:
            f1, f2 = rng.uniform(0.95, 1.60), rng.uniform(1.80, 3.20); sp = (4*np.pi*s/n_sub)[:, None]
            mod = 1.4*np.sin(2*np.pi*f1*t[None, :]+sp) + 1.1*np.cos(2*np.pi*f2*t[None, :]-sp)
        cf = rng.uniform(0.20, 0.56)
        clutter = 1.35*np.sin(2*np.pi*cf*t[None, :] + rng.uniform(0, 2*np.pi, size=(n_sub, 1)))
        amp = np.abs(base + mod + clutter + rng.normal(0, 1.55, size=(n_sub, T))).astype(np.float32)
        nm = csi_bench_power_normalize(amp); X[i] = (nm - nm.mean(-1, keepdims=True))/(nm.std(-1, keepdims=True)+1e-6)
    perm = rng.permutation(n_total); X, y = X[perm], y[perm]
    return X[:n_train], y[:n_train], X[n_train:], y[n_train:]

def bank(X, n_osc=12, fs=30.0, nonlinear=True, seed=42):
    rng = np.random.RandomState(seed); N, C, T = X.shape; dt = 1/fs
    omega = 2*np.pi*np.linspace(0.15, 2.5, n_osc); mu = np.full(n_osc, -0.25)
    W_enc = (rng.randn(n_osc, C) + 1j*rng.randn(n_osc, C))*(0.6/math.sqrt(C))
    W_coup = (rng.randn(n_osc, n_osc) + 1j*rng.randn(n_osc, n_osc))*(0.08 if nonlinear else 0.0); np.fill_diagonal(W_coup, 0)
    I_raw = np.transpose(X, (0, 2, 1)) @ W_enc.T; I_enc = 2.5*(np.tanh(I_raw.real) + 1j*np.tanh(I_raw.imag))
    lam = mu[None, :] + 1j*omega[None, :]
    if nonlinear:
        zz = np.full((N, n_osc), 0.01+0.01j); traj = np.zeros((N, T, n_osc), complex); traj[:, 0] = zz; clipped = 0
        f = lambda zv, Iv: lam*zv - (1+0.1j)*(np.abs(zv)**2)*zv + zv @ W_coup.T + Iv
        for t in range(T-1):
            I0, I1 = I_enc[:, t], I_enc[:, t+1]; Im = 0.5*(I0+I1)
            k1 = dt*f(zz, I0); k2 = dt*f(zz+0.5*k1, Im); k3 = dt*f(zz+0.5*k2, Im); k4 = dt*f(zz+k3, I1)
            zz = zz + (k1+2*k2+2*k3+k4)/6; amp = np.abs(zz); clipped += np.sum(amp > 4.0)
            zz = zz*(np.minimum(amp, 4.0)/(amp+1e-8)); traj[:, t+1] = zz
        return traj, I_enc, clipped
    else:
        tv = np.arange(T)[:, None]*dt; kern = np.exp(lam*tv); L = 512
        traj = np.fft.ifft(np.fft.fft(I_enc, n=L, axis=1)*np.fft.fft(kern, n=L, axis=0)[None], axis=1)[:, :T]
        return traj, I_enc, 0

Xtr, ytr, Xte, yte = generate()
trN, I_enc, clipped = bank(Xtr, nonlinear=True)
trL, _, _ = bank(Xtr, nonlinear=False)
r2 = np.abs(trN)**2
print("\nOscillator bank regime (CSI-Bench synthetic train set, 160 windows x 150 samples x 12 osc):")
print(f"  |I_enc| median={np.median(np.abs(I_enc)):.2f}, 95th pct={np.percentile(np.abs(I_enc),95):.2f}")
print(f"  NL bank |z|^2: median={np.median(r2):.3f}, mean={r2.mean():.3f}; fraction of samples with |z|^2 > |mu|=0.25: {np.mean(r2 > 0.25):.3f}; amplitude-clip (|z|>4) events: {clipped}")
pN = np.log(np.mean(np.abs(trN)**2, axis=1)+1e-6); pL = np.log(np.mean(np.abs(trL)**2, axis=1)+1e-6)
cors = [np.corrcoef(pN[:, j], pL[:, j])[0, 1] for j in range(12)]
print("  per-oscillator corr(NL log-power, linear log-power) across windows:", np.round(cors, 3))
print("  note: linear bank kernel exp((mu+i w)t) has unit input gain, i.e., discrete sum without dt factor -> scale differs by 1/dt=30")

# ---- Hampel checks ----
def hampel_centered(x, w=15, k=3.0):
    h = w//2; xp = np.pad(x, (h, h), mode='reflect'); W = np.lib.stride_tricks.sliding_window_view(xp, w)
    med = np.median(W, -1); mad = 1.4826*np.median(np.abs(W - med[:, None]), -1) + 1e-8
    m = np.abs(x - med) > k*mad; return np.where(m, med, x), m
g = np.random.default_rng(3).standard_normal(200000)
_, m = hampel_centered(g); print(f"\nHampel (w=15, 3 sigma) false-flag rate on pure Gaussian noise: {m.mean()*100:.2f}% (asymptotic 2-sided 3-sigma rate 0.27%)")
tt = np.arange(4000)/100.0; s = 0.05*np.sin(2*np.pi*0.25*tt) + 0.005*np.random.default_rng(4).standard_normal(4000)
_, m2 = hampel_centered(s); print(f"  on 0.25 Hz tone + small noise (SNR ~17 dB) at fs=100: flagged {m2.mean()*100:.2f}%")
step = np.r_[np.zeros(2000), 2*np.pi*np.ones(2000)] + 0.01*np.random.default_rng(5).standard_normal(4000)
y3, m3 = hampel_centered(step); print(f"  2*pi unwrap-error step: output after filter still has step of {np.median(y3[2100:])-np.median(y3[:1900]):.3f} rad (Hampel cannot remove level shifts)")
