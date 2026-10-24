import numpy as np, scipy.signal as sig, math, time

# ---- exact copies of project functions (cell_06.py) ----
def integrate_hopf_rk4(F_t, f0_hz=0.25, mu=1.0, K=1.65, eps_omega=2.40, dt=0.01, seed_from_zc=True):
    analytic = sig.hilbert(F_t)
    F_r = F_t.astype(np.float64); F_i = np.imag(analytic).astype(np.float64); T = len(F_t)
    if seed_from_zc and np.std(F_t) > 0.08 and T >= 200:
        interior = F_t[int(0.1 * T): int(0.9 * T)]; interior = interior - np.mean(interior)
        zc = np.where(np.diff(np.signbit(interior)))[0]
        if len(zc) >= 2:
            zc_hz = 1.0 / (2.0 * np.mean(np.diff(zc)) * dt + 1e-8)
            if 0.10 <= zc_hz <= 0.60:
                f0_hz = float(zc_hz)
    omega = 2.0 * math.pi * f0_hz
    traj = np.zeros((T, 2)); omega_hist = np.zeros(T)
    x, y = math.sqrt(max(mu, 0.1)), 0.0
    traj[0] = [x, y]; omega_hist[0] = omega
    def rhs(xv, yv, wv, fr, fi):
        r2 = xv * xv + yv * yv; r = math.sqrt(r2 + 1e-8); f_mag = math.hypot(fr, fi)
        mu_eff = mu * min(1.0, f_mag / 0.25) if f_mag < 0.25 else mu
        return ((mu_eff - r2) * xv - wv * yv + K * fr, (mu_eff - r2) * yv + wv * xv + K * fi, eps_omega * (fi * xv - fr * yv) / r)
    for t in range(T - 1):
        f0r, f1r = F_r[t], F_r[t + 1]; f0i, f1i = F_i[t], F_i[t + 1]
        fmr, fmi = 0.5 * (f0r + f1r), 0.5 * (f0i + f1i)
        k1 = rhs(x, y, omega, f0r, f0i)
        k2 = rhs(x + 0.5*dt*k1[0], y + 0.5*dt*k1[1], omega + 0.5*dt*k1[2], fmr, fmi)
        k3 = rhs(x + 0.5*dt*k2[0], y + 0.5*dt*k2[1], omega + 0.5*dt*k2[2], fmr, fmi)
        k4 = rhs(x + dt*k3[0], y + dt*k3[1], omega + dt*k3[2], f1r, f1i)
        x += (dt/6)*(k1[0]+2*k2[0]+2*k3[0]+k4[0]); y += (dt/6)*(k1[1]+2*k2[1]+2*k3[1]+k4[1])
        omega += (dt/6)*(k1[2]+2*k2[2]+2*k3[2]+k4[2])
        omega = min(max(omega, 2*math.pi*0.08), 2*math.pi*0.65)
        r = math.hypot(x, y)
        if r > 4.0: x, y = x*4.0/r, y*4.0/r
        traj[t+1] = [x, y]; omega_hist[t+1] = omega
    return traj, omega_hist

def plv_metrics(F_t, traj_xy, fs=100.0, window_samples=200):
    analytic_chest = sig.hilbert(F_t); theta_chest = np.angle(analytic_chest)
    x, y = traj_xy[:, 0], traj_xy[:, 1]; theta_osc = np.arctan2(y, x); r_t = np.hypot(x, y)
    phasor = np.exp(1j * (theta_chest - theta_osc))
    kernel = np.ones(window_samples) / window_samples; pw = window_samples // 2
    re_s = np.convolve(np.pad(phasor.real, (pw, pw), mode="reflect"), kernel, mode="valid")[:len(F_t)]
    im_s = np.convolve(np.pad(phasor.imag, (pw, pw), mode="reflect"), kernel, mode="valid")[:len(F_t)]
    plv_raw = np.hypot(re_s, im_s)
    env = np.abs(analytic_chest)
    env_smooth = np.convolve(np.pad(env, (pw, pw), mode="reflect"), kernel, mode="valid")[:len(F_t)]
    env_gate = np.clip(env_smooth / 0.22, 0.0, 1.0)
    T = len(F_t); unwrapped = np.unwrap(theta_osc)
    pad_start = min(int(2.2*fs), T//3); pad_end = min(int(0.5*fs), T//10)
    t_start, t_end = max(0, pad_start), T - pad_end
    if t_end - t_start < int(2.0*fs): t_start, t_end = 0, T
    f_inst = abs(unwrapped[t_end-1] - unwrapped[t_start]) / (2*math.pi*((t_end-1-t_start)/fs))
    return dict(plv_raw=plv_raw, plv_gated=plv_raw*env_gate, env_gate=env_gate, f_inst=f_inst, r_t=r_t,
                t_start=t_start, t_end=t_end, theta_chest=theta_chest, theta_osc=theta_osc)

fs = 100.0
sos = sig.butter(4, [0.12, 0.60], btype='bandpass', fs=fs, output='sos')
rng = np.random.default_rng(12345)

def bl_noise(n, rng):
    w = rng.standard_normal(n + 6000)
    y = sig.sosfilt(sos, w)[6000:]
    return y / y.std()

# Rice zero-crossing frequency of the band (sqrt(m2/m0)) and spectral centroid
fg = np.linspace(0.001, 5, 50000); _, Hb = sig.sosfreqz(sos, worN=fg, fs=fs); S = np.abs(Hb)**2
m0 = np.trapezoid(S, fg); m1 = np.trapezoid(fg*S, fg); m2 = np.trapezoid(fg**2*S, fg)
print(f"Band-limited noise (0.12-0.60 Hz Butterworth^2 PSD): centroid m1/m0={m1/m0:.3f} Hz ({60*m1/m0:.1f} BPM); Rice sqrt(m2/m0)={math.sqrt(m2/m0):.3f} Hz ({60*math.sqrt(m2/m0):.1f} BPM)")

for (label, T_sec, eps, mu) in [("40-s window, eps=0.95, mu=0.5 (demo/calib)", 40, 0.95, 0.5),
                                ("6-s window, eps=2.4, mu=1.0 (HIL runtime)", 6, 2.4, 1.0)]:
    n = int(T_sec*fs)
    res = {"sine": [], "noise": []}
    for trial in range(40):
        # clean sinusoid with random rate 10-30 BPM
        f_true = rng.uniform(10, 30)/60
        tt = np.arange(n)/fs
        s = np.sin(2*np.pi*f_true*tt + rng.uniform(0, 2*np.pi)); s /= s.std()
        tr, om = integrate_hopf_rk4(s, mu=mu, K=1.65, eps_omega=eps, dt=1/fs)
        m = plv_metrics(s, tr, fs)
        a, b = m['t_start'], m['t_end']
        res["sine"].append((np.mean(m['plv_raw'][a:b]), np.mean(m['plv_raw'][a:b] < 0.15), np.mean(m['plv_raw'][a:b] < 0.6), 60*m['f_inst'], 60*f_true))
        # pure band-limited Gaussian noise, no breathing at all
        z = bl_noise(n, rng)
        tr, om = integrate_hopf_rk4(z, mu=mu, K=1.65, eps_omega=eps, dt=1/fs)
        m = plv_metrics(z, tr, fs)
        res["noise"].append((np.mean(m['plv_raw'][a:b]), np.mean(m['plv_raw'][a:b] < 0.15), np.mean(m['plv_raw'][a:b] < 0.6), 60*m['f_inst'], np.mean(m['plv_gated'][a:b])))
    s_ = np.array(res["sine"]); z_ = np.array(res["noise"])
    print(f"\n[{label}] 40 trials")
    print(f"  clean sinusoid: mean PLV={s_[:,0].mean():.3f}; frac time PLV<0.15={s_[:,1].mean():.3f}; <0.6={s_[:,2].mean():.3f}; rate err mean|.|={np.mean(np.abs(s_[:,3]-s_[:,4])):.2f} BPM")
    print(f"  pure band-limited NOISE: mean PLV={z_[:,0].mean():.3f} (min trial {z_[:,0].min():.3f}); frac time PLV<0.15={z_[:,1].mean():.3f}; <0.6={z_[:,2].mean():.3f}; gated PLV mean={z_[:,4].mean():.3f}")
    print(f"  reported 'breathing rate' on pure noise: mean={z_[:,3].mean():.1f} BPM, sd={z_[:,3].std():.1f}, range=[{z_[:,3].min():.1f},{z_[:,3].max():.1f}]")

# Null distribution: PLV between two INDEPENDENT band-limited noises, project-style centered 2-s window
print("\nNull PLV between Hilbert phases of two INDEPENDENT 0.12-0.60 Hz noises (2-s centered window, fs=100):")
vals = []
for trial in range(200):
    a = bl_noise(4000, rng); b = bl_noise(4000, rng)
    pa = np.angle(sig.hilbert(a)); pb = np.angle(sig.hilbert(b))
    ph = np.exp(1j*(pa-pb)); k = np.ones(200)/200
    plv = np.abs(np.convolve(ph, k, mode='valid'))
    vals.append(plv[::50])
vals = np.concatenate(vals)
print(f"  mean={vals.mean():.3f}, median={np.median(vals):.3f}, 5th pct={np.percentile(vals,5):.3f}, frac<0.15={np.mean(vals<0.15):.3f}, frac<0.6={np.mean(vals<0.6):.3f}, frac>0.9={np.mean(vals>0.9):.3f}")
for win_s in [4, 8, 16, 32]:
    vv = []
    for trial in range(100):
        a = bl_noise(6000, rng); b = bl_noise(6000, rng)
        ph = np.exp(1j*(np.angle(sig.hilbert(a)) - np.angle(sig.hilbert(b))))
        k = np.ones(int(win_s*fs))/int(win_s*fs)
        vv.append(np.abs(np.convolve(ph, k, mode='valid'))[::100])
    vv = np.concatenate(vv)
    print(f"  window {win_s:2d} s: mean null PLV={vv.mean():.3f}, 95th pct={np.percentile(vv,95):.3f}")
print("  (i.i.d. uniform phases reference: E[PLV] ~ sqrt(pi/(4N)); N=200 -> %.3f)" % math.sqrt(math.pi/800))

# Apnea scenario similar to project demo: 15 BPM, apnea 17-23 s, small residual noise, whole-window unit-std normalization
print("\nApnea scenario (24 s, 15 BPM, apnea 17-23 s, residual noise std 0.05 of breathing amplitude):")
n = 2400; tt = np.arange(n)/fs
x = np.sin(2*np.pi*0.25*tt); ap = (tt >= 17) & (tt <= 23); x[ap] = 0
x = x + 0.05*bl_noise(n, rng)
x /= x.std()
tr, om = integrate_hopf_rk4(x, mu=0.5, K=1.65, eps_omega=0.95, dt=1/fs)
m = plv_metrics(x, tr, fs)
core = (tt >= 18.5) & (tt <= 22)
print(f"  during apnea core (18.5-22 s): raw PLV mean={m['plv_raw'][core].mean():.3f}, env_gate mean={m['env_gate'][core].mean():.3f}, gated PLV mean={m['plv_gated'][core].mean():.3f}, r mean={m['r_t'][core].mean():.3f}")
pre = (tt >= 5) & (tt <= 15)
print(f"  during breathing (5-15 s): raw PLV mean={m['plv_raw'][pre].mean():.3f}, gated={m['plv_gated'][pre].mean():.3f}, r mean={m['r_t'][pre].mean():.3f}")
# Same apnea but residual noise larger (e.g., 0.3) -> does raw PLV drop?
for nz in [0.2, 0.5]:
    x = np.sin(2*np.pi*0.25*tt); x[ap] = 0; x = x + nz*bl_noise(n, rng); x /= x.std()
    tr, om = integrate_hopf_rk4(x, mu=0.5, K=1.65, eps_omega=0.95, dt=1/fs)
    m = plv_metrics(x, tr, fs)
    print(f"  residual noise {nz}: apnea-core raw PLV={m['plv_raw'][core].mean():.3f}, env_gate={m['env_gate'][core].mean():.3f}, gated PLV={m['plv_gated'][core].mean():.3f}")

# Rate estimation comparison on 6-s windows: oscillator vs simple estimators, sinusoid + band-limited noise
print("\nRate estimation on 6-s windows (fs=100), true 10-30 BPM sinusoid + in-band noise, 100 trials each:")
def fft_peak(xw, fs, nfft=8192):
    f = np.fft.rfftfreq(nfft, 1/fs); P = np.abs(np.fft.rfft((xw-xw.mean())*np.hanning(len(xw)), nfft))**2
    msk = (f >= 0.1) & (f <= 0.7); return f[msk][np.argmax(P[msk])]
for snr_db in [20, 10, 3, 0]:
    e_osc, e_fft, e_hil = [], [], []
    for trial in range(100):
        f_true = rng.uniform(10, 30)/60; n = 600; tt = np.arange(n)/fs
        s = np.sin(2*np.pi*f_true*tt + rng.uniform(0, 2*np.pi)); s /= s.std()
        z = bl_noise(n, rng); x = s + z*10**(-snr_db/20); x /= x.std()
        tr, om = integrate_hopf_rk4(x, mu=1.0, K=1.65, eps_omega=2.4, dt=1/fs)
        m = plv_metrics(x, tr, fs)
        e_osc.append(60*(m['f_inst'] - f_true))
        e_fft.append(60*(fft_peak(x, fs) - f_true))
        ph = np.unwrap(np.angle(sig.hilbert(x))); a, b = m['t_start'], m['t_end']
        e_hil.append(60*((ph[b-1]-ph[a])/(2*np.pi*(b-1-a)/fs) - f_true))
    f = lambda e: (np.sqrt(np.mean(np.square(e))), np.mean(np.abs(e)))
    print(f"  SNR {snr_db:2d} dB: oscillator RMSE={f(e_osc)[0]:.2f} BPM | Hilbert phase-slope (same span, no oscillator) RMSE={f(e_hil)[0]:.2f} | zero-padded Hann FFT peak RMSE={f(e_fft)[0]:.2f}; corr(osc err, Hilbert err)={np.corrcoef(e_osc, e_hil)[0,1]:.2f}")
