"""Export compact JSON for the redesigned dashboard (precomputed with hinigram_live, identical to the in-browser DSP)."""
import json, os, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the bundle folder
sys.path.insert(0, ROOT)
import numpy as np
import hinigram_live as hl
import semi_gen

SRC = os.path.join(ROOT, "demo_20261019_024431.csv")
DEMO = os.path.join(ROOT, "semi", "demo_semisynthetic.csv")    # written by semi_gen.make_demo()
SEATS = ["A", "B", "C"]


def fnum(a, nd=3):
    out = []
    for v in np.asarray(a, float):
        out.append(None if not np.isfinite(v) else round(float(v), nd))
    return out


def display_wave(F, T, cfg):
    """Sign-aligned concatenation of the last hop of each window's respiratory component (10 Hz)."""
    fs = F.fs
    nw, nh = int(cfg.win_s * fs), int(cfg.hop_s * fs)
    vals, prev = [], None
    for i, e in enumerate(range(nw, len(F.t) + 1, nh)):
        r = hl.estimate_window(F.X[e - nw:e], fs, cfg)
        w = r["waveform"] / (np.std(r["waveform"]) + 1e-12)
        if prev is not None:
            L = min(len(prev), len(w) - nh)
            if np.dot(prev[-L:], w[len(w) - nh - L:len(w) - nh]) < 0:
                w = -w
        vals.extend(w[-nh:].tolist())
        prev = w
    t0 = float(F.t[nw - nh]) if len(F.t) >= nw else float(F.t[0])
    return dict(t0=round(t0, 3), fs=fs, v=[round(float(x), 3) for x in vals])


def series_2hz(L, F, t_end):
    tg = np.arange(5.0, t_end, 0.5)
    rate = hl.rolling_rate(L, tg, 5.0)
    amp = np.abs(L.H[:, hl.valid_slots(bool(L.first_word_invalid[0]))])
    mdb = 20 * np.log10(np.sqrt(np.mean(amp ** 2, axis=1)) + 1e-9)
    step = np.r_[0, np.abs(np.diff(mdb)) > 1.5].astype(float)
    lo = np.searchsorted(L.t, tg - 5.0); hi = np.searchsorted(L.t, tg)
    cs = np.cumsum(np.r_[0, step])
    share = (cs[hi] - cs[lo]) / np.maximum(hi - lo, 1) * 100
    rssi = np.interp(tg, F.t, np.convolve(F.rssi, np.ones(10) / 10, mode="same"))
    act = np.interp(tg, F.t, F.activity)
    return dict(t=fnum(tg, 2), rate=fnum(rate, 2), rssi=fnum(rssi, 1), steps=fnum(share, 1), act=fnum(act, 3))


def export(path, profiles, truth_scen=None, title="", note=""):
    S = hl.load_csi_session(path)
    t_end = min(float(L.t[-1]) for L in S.links.values())
    sensors = []
    for i, mac in enumerate(S.macs):
        prof = profiles.get(mac, "adult")
        cfg = hl.RRConfig(profile=prof)
        L = S.links[mac]
        F = hl.link_features(L, fs=cfg.fs, t_end=t_end)
        T = hl.track_link(F, cfg)
        h = hl.link_health(L)
        keys = []
        for st, why in zip(T.status, T.reason):
            keys.append(why)
        d = dict(mac=mac, label=f"Sensor {i + 1}", seat=SEATS[i] if i < len(SEATS) else str(i + 1), profile=prof,
                 health={k: (round(v, 3) if isinstance(v, float) else v) for k, v in h.items()},
                 hops=dict(t=fnum(T.t, 2), status=T.status, reason=T.reason, bpm=fnum(T.bpm, 2), raw=fnum(T.bpm_raw, 2),
                           q=fnum(T.quality, 3), rel=[bool(x) for x in T.reliable], mot=[bool(x) for x in T.motion],
                           pause=fnum(T.pause_s, 1), snr=fnum(T.pause_snr, 2)),
                 wave=display_wave(F, T, cfg), series=series_2hz(L, F, t_end))
        if truth_scen is not None:
            sc = truth_scen[mac]
            tg = np.arange(0, t_end, 1.0)
            _, b = hl.breathing_waveform(tg, sc)
            d["truth"] = dict(t=fnum(tg, 1), bpm=fnum(np.where(b > 0, b, np.nan), 2), scenario=sc.name,
                              segments=[list(map(float, s)) for s in sc.segments], depth=sc.depth)
        sensors.append(d)
    t0_host = S.t0_host
    start = datetime.datetime.fromtimestamp(t0_host, datetime.timezone(datetime.timedelta(hours=8))).isoformat() if np.isfinite(t0_host) else None
    return dict(file=os.path.basename(path), title=title, note=note, duration=round(S.duration_s, 2),
                packets=sum(len(L.t) for L in S.links.values()), start=start, sensors=sensors)


if __name__ == "__main__":
    macs = semi_gen.MACS
    demo_scen = {m: hl.BreathingScenario(semi_gen.SCEN[n], depth=d, phase_depth=d, seed=77 + i, name=n)
                 for i, (m, (n, d, p)) in enumerate(semi_gen.DEMO.items())}
    demo_prof = {m: p for m, (n, d, p) in semi_gen.DEMO.items()}
    if not os.path.exists(DEMO):
        semi_gen.make_demo(DEMO)       # real packets plus known breathing (seeds 77-79)
    data = {
        "version": "Hinigram v1.3.2",
        "generated": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "sources": {
            "demo": export(DEMO, demo_prof, demo_scen, title="Demo scenario",
                           note="Real packets from the format sample with simulated breathing added (5% modulation)."),
            "sample": export(SRC, {}, None, title="Format sample",
                             note="The real recording from the three ESP32 nodes. It has no breathing reference."),
        },
    }
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dashboard", "dashboard_data.json")
    json.dump(data, open(out, "w"), separators=(",", ":"))
    print("wrote", out, os.path.getsize(out), "bytes")
