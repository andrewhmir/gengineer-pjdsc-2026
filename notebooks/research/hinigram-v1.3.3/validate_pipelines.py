"""Head-to-head validation of the v1.2 (legacy) and v1.3 pipelines on semi-synthetic CSVs.

Semi-synthetic = the real 173 s recording from the nodes (demo_20261019_024431.csv) with breathing
of known rate modulated onto its packets. Both pipelines see the identical files and are scored on
identical 30 s windows ending every 2 s.
"""
import json, math, time
import numpy as np
import scipy.signal as sig
import hinigram_live as hl
import legacy_v12 as L
from semi_gen import make, SCEN, MACS, SRC, PROFILE

WIN = 30.0


def legacy_window(info, t_end, win=WIN):
    """Replicates v1.2 Section 8 `analyze_pjdsc_session_with_resonet` on one trailing window."""
    t_rel = info["t_pc"] - info["t_pc"][0]
    m = (t_rel > t_end - win) & (t_rel <= t_end)
    if m.sum() < 60:
        return np.nan, np.nan, "NA"
    H_raw = info["H_matrix"][:, m]
    t_w = t_rel[m] - t_rel[m][0]
    dur = float(t_w[-1])
    T_uni = int(dur * 30.0)
    t_uni = np.linspace(0.0, dur, T_uni)
    H_uni = np.zeros((56, T_uni), dtype=np.complex64)
    for k in range(56):
        H_uni[k] = np.interp(t_uni, t_w, H_raw[k].real) + 1j * np.interp(t_uni, t_w, H_raw[k].imag)
    _, _, phase_cscr, _ = L.compute_cscr_transform(H_uni, min_spacing=6)
    cleansed, _ = L.unwrap_and_hampel_filter(phase_cscr, window_size=9)
    F_t, _, _, _ = L.fens_and_fastica_isolation(cleansed, fs=30.0, causal_mode=False)
    traj, _ = L.integrate_hopf_rk4(F_t, f0_hz=0.25, mu=1.0, K=1.65, eps_omega=2.20, dt=1.0 / 30.0)
    mm = L.compute_plv_and_respiratory_metrics(F_t, traj, fs=30.0, window_samples=int(4.0 * 30.0))
    tier, _, _ = L.evaluate_triage_state(mm["bpm_est"], mm["plv_current"], mm["r_t"], mm["f_inst_hz"])
    return float(mm["bpm_est"]), float(mm["plv_current"]), tier


def truth_status(sc, t_end, profile):
    """Reference screening status from the injected truth (pause >= profile minimum => urgent)."""
    tg = np.arange(max(0, t_end - WIN), t_end + 1e-9, 0.05)
    _, bpm = hl.breathing_waveform(tg, sc)
    pause_min = 10.0 if profile == "adult" else 20.0
    # length of the current pause run at t_end
    run = 0.0
    for v in bpm[::-1]:
        if v > 0:
            break
        run += 0.05
    if run >= pause_min:
        return "urgent"
    seg = bpm[bpm > 0]
    if len(seg) < 0.8 * len(bpm):
        return "transition"
    lvl, _ = hl.classify_rate(float(np.mean(seg)), profile)
    return lvl


LEGACY_TO_STATUS = {"RED": "urgent", "YELLOW": "watch", "GREEN": "typical", "NA": "no_reading"}


def run_file(path, scs, profile):
    S = hl.load_csi_session(path)
    cfg = hl.RRConfig(profile=profile)
    tracks = hl.analyze_session(S, cfg)
    sess_legacy = L.load_pjdsc_session(path)
    rows = []
    for mac in MACS:
        T = tracks[mac]
        truth = hl.truth_on_grid(scs[mac], T.t, WIN) if scs else np.full(len(T.t), np.nan)
        info = sess_legacy[mac]
        for i, te in enumerate(T.t):
            lb, lplv, ltier = legacy_window(info, te)
            ts = truth_status(scs[mac], te, profile) if scs else "absent"
            rows.append(dict(mac=mac, depth=(scs[mac].depth if scs else 0.0), t=float(te), truth=float(truth[i]),
                             truth_status=ts, new_bpm=float(T.bpm[i]), new_raw=float(T.bpm_raw[i]),
                             new_reliable=bool(T.reliable[i]), new_status=T.status[i], new_motion=bool(T.motion[i]),
                             new_prom=float(T.prominence[i]), new_acf=float(T.acf[i]),
                             legacy_bpm=lb, legacy_plv=lplv, legacy_status=LEGACY_TO_STATUS.get(ltier, ltier)))
    return rows


if __name__ == "__main__":
    t0 = time.time()
    all_rows = []
    for seed in [1, 2]:
        for name in SCEN:
            path, scs = make(name, seed)
            prof = PROFILE.get(name, "adult")
            for r in run_file(path, scs, prof):
                r.update(scenario=name, seed=seed, profile=prof)
                all_rows.append(r)
            print(f"{name} s{seed} done {time.time() - t0:.0f}s", flush=True)
    for r in run_file(SRC, None, "adult"):
        r.update(scenario="live_raw", seed=0, profile="adult")
        all_rows.append(r)
    json.dump(all_rows, open("validation_rows.json", "w"))
    print("rows", len(all_rows), "time %.0fs" % (time.time() - t0))
