import numpy as np, scipy.signal as sig, math, importlib.util, sys
spec = importlib.util.spec_from_file_location("plvsim_funcs", "plv_sim.py")
src = open("plv_sim.py").read().split("fs = 100.0\nsos =")[0]   # function defs only
ns = {}; exec(src, ns)
integrate, plv_metrics = ns["integrate_hopf_rk4"], ns["plv_metrics"]
fs = 100.0; sos = sig.butter(4, [0.12, 0.60], btype='bandpass', fs=fs, output='sos')
rng = np.random.default_rng(7)
def bl_noise(n):
    w = rng.standard_normal(n + 6000); y = sig.sosfilt(sos, w)[6000:]; return y / y.std()
for snr_db in [20, 10, 3]:
    e_seed, e_cold, e_zc = [], [], []
    for trial in range(100):
        f_true = rng.uniform(10, 30)/60; n = 600; tt = np.arange(n)/fs
        s = np.sin(2*np.pi*f_true*tt + rng.uniform(0, 2*np.pi)); s /= s.std()
        x = s + bl_noise(n)*10**(-snr_db/20); x /= x.std()
        tr, _ = integrate(x, mu=1.0, K=1.65, eps_omega=2.4, dt=1/fs, seed_from_zc=True); e_seed.append(60*(plv_metrics(x, tr, fs)['f_inst'] - f_true))
        tr, _ = integrate(x, mu=1.0, K=1.65, eps_omega=2.4, dt=1/fs, seed_from_zc=False); e_cold.append(60*(plv_metrics(x, tr, fs)['f_inst'] - f_true))
        interior = x[int(0.1*n):int(0.9*n)]; interior = interior - interior.mean()
        zc = np.where(np.diff(np.signbit(interior)))[0]
        fz = 1.0/(2.0*np.mean(np.diff(zc))/fs) if len(zc) >= 2 else 0.25
        e_zc.append(60*(fz - f_true))
    r = lambda e: np.sqrt(np.mean(np.square(e)))
    print(f"SNR {snr_db:2d} dB, 6-s windows: RMSE project (ZC look-ahead seed) = {r(e_seed):.2f} BPM | true cold start f0=0.25 Hz = {r(e_cold):.2f} BPM | ZC seed alone = {r(e_zc):.2f} BPM")
