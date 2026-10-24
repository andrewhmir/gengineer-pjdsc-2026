"""
hinigram_live.py  (Hinigram v1.3.2)
===================================
Audited ingestion + respiratory-rate pipeline for the ESP32 ``CSI_DATA`` text
logs produced by the team's logger (e.g. ``csi_logs/demo_20261019_024431.csv``).

What this module does differently from v1.2 (see the audit report for why):

1. **Format-faithful parsing.** One parser for the esp-csi line format, with or
   without a leading host timestamp. Packets are demultiplexed by transmitter
   MAC, so the three links are never mixed into one time series.
2. **Correct subcarrier map.** ESP32 reports LLTF (HT20, no secondary channel)
   as 64 slots ordered ``[0..31, -32..-1]``. Valid data subcarriers are
   ``-26..-1`` (slots 38-63) and ``+1..+26`` (slots 1-26); slots 27-37 are
   guard/null, slot 0 is DC. When ``first_word_invalid == 1`` slots 0-1 are
   corrupt, leaving 51 usable subcarriers.
3. **Receiver clock as time base.** ``local_timestamp`` (us, 32-bit, wraps every
   ~71.6 min) comes from the single receiver for all links, so it aligns links
   exactly and has far less jitter than host (PC) arrival times.
4. **Gain-step and phase-offset removal per packet.** Amplitude is divided by
   the packet's RMS amplitude (removes AGC/FFT scaling steps); phase is
   unwrapped across frequency and its linear trend removed (CFO + STO/SFO).
5. **Window-level causal estimation with a signal-quality gate.** Every hop,
   the last ``win_s`` seconds are analysed (PCA over subcarrier channels ->
   spectral peak + autocorrelation). A rate is reported only when the two
   estimators agree and the spectral peak is prominent; otherwise the output
   is "no reliable reading". Motion windows are flagged and withheld. Since
   v1.3.2 a rate is also withheld when the newest block of the window holds no
   breathing (recency check), so a window cannot vouch for breaths that ended
   many seconds ago.
6. **Screening flags, not diagnoses.** Adult flags follow NEWS2 respiratory
   bands; child profiles follow WHO IMCI fast-breathing cut-offs. A breathing
   pause is flagged only relative to the person's own recent breathing
   amplitude, and only after a minimum duration.
7. **Semi-synthetic injection.** ``inject_breathing`` writes a new CSV in the
   identical format with breathing of known rate modulated onto the real
   packets (keeping their loss, jitter, quantisation and gain steps), so the
   pipeline can be validated end-to-end against known ground truth.

Only numpy and scipy are required.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import scipy.signal as sig

# --------------------------------------------------------------------------- #
# 1. ESP32 CSI format constants
# --------------------------------------------------------------------------- #
ESP32_SLOT_TO_SUBCARRIER = np.r_[np.arange(0, 32), np.arange(-32, 0)]
ESP32_LLTF_DATA_SLOTS = np.r_[np.arange(1, 27), np.arange(38, 64)]          # 52 slots
ESP32_GUARD_SLOTS = np.r_[np.arange(27, 38)]                                # 11 slots (27..37)
HEADER_FIELDS = [
    "type", "seq", "mac", "rssi", "rate", "sig_mode", "mcs", "bandwidth", "smoothing",
    "not_sounding", "aggregation", "stbc", "fec_coding", "sgi", "noise_floor", "ampdu_cnt",
    "channel", "secondary_channel", "local_timestamp", "ant", "sig_len", "rx_state", "len",
    "first_word_invalid",
]
TS_WRAP = 2 ** 32          # local_timestamp is uint32 microseconds
SEQ_WRAP = 2 ** 16         # conservative guard for sender counters


def valid_slots(first_word_invalid: bool = True) -> np.ndarray:
    """Usable LLTF slots in frequency order (-26..-1, then +1/+2..+26)."""
    slots = ESP32_LLTF_DATA_SLOTS
    if first_word_invalid:
        slots = slots[slots >= 2]
    sc = ESP32_SLOT_TO_SUBCARRIER[slots]
    return slots[np.argsort(sc)]


# --------------------------------------------------------------------------- #
# 2. Parsing & loading
# --------------------------------------------------------------------------- #
def parse_csi_line(line: str) -> Optional[dict]:
    """Parse one esp-csi ``CSI_DATA`` line (optionally prefixed by a host timestamp)."""
    s = line.strip()
    if "CSI_DATA" not in s:
        return None
    b, e = s.find("["), s.rfind("]")
    if b < 0 or e < b:
        return None
    hdr = [h.strip() for h in s[:b].replace('"', "").rstrip(",").split(",")]
    try:
        k = hdr.index("CSI_DATA")
    except ValueError:
        return None
    if len(hdr) < k + len(HEADER_FIELDS):
        return None
    try:
        vals = np.array(s[b + 1:e].split(","), dtype=np.int16)
        rec = {
            "t_host": float(hdr[0]) if k > 0 else float("nan"),
            "seq": int(hdr[k + 1]),
            "mac": hdr[k + 2].lower(),
            "rssi": int(hdr[k + 3]),
            "sig_mode": int(hdr[k + 5]),
            "bandwidth": int(hdr[k + 7]),
            "noise_floor": int(hdr[k + 14]),
            "channel": int(hdr[k + 16]),
            "secondary_channel": int(hdr[k + 17]),
            "ts_us": int(hdr[k + 18]),
            "sig_len": int(hdr[k + 20]),
            "rx_state": int(hdr[k + 21]),
            "len": int(hdr[k + 22]),
            "first_word_invalid": int(hdr[k + 23]),
            "raw": vals,
            "header": hdr,
            "prefix_fields": k,
        }
    except (ValueError, IndexError):
        return None
    return rec


@dataclass
class LinkStream:
    """All packets from one transmitter MAC, in arrival order."""
    mac: str
    t: np.ndarray            # seconds, receiver clock, session-relative
    t_host: np.ndarray       # seconds, host clock, session-relative (NaN if absent)
    seq: np.ndarray
    rssi: np.ndarray
    channel: np.ndarray
    noise_floor: np.ndarray
    first_word_invalid: np.ndarray
    H: np.ndarray            # (N, 64) complex64, raw slots (slots 0-1 NaN if corrupt)
    label: str = ""


@dataclass
class CSISession:
    path: str
    links: Dict[str, LinkStream]
    n_lines: int
    n_bad: int
    t0_receiver_us: int
    t0_host: float
    duration_s: float
    lengths_seen: Dict[int, int] = field(default_factory=dict)

    @property
    def macs(self) -> List[str]:
        return sorted(self.links)


def _unwrap_counter(x: np.ndarray, wrap: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.int64)
    d = np.diff(x)
    jumps = np.where(d < -wrap // 2, wrap, 0)
    return x + np.r_[0, np.cumsum(jumps)]


def load_csi_session(path: str, max_lines: Optional[int] = None) -> CSISession:
    """Load an esp-csi log into per-MAC :class:`LinkStream` objects."""
    groups: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    n_lines = n_bad = 0
    lengths: Dict[int, int] = defaultdict(int)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            n_lines += 1
            if max_lines and n_lines > max_lines:
                break
            r = parse_csi_line(line)
            if r is None:
                n_bad += 1
                continue
            lengths[r["len"]] += 1
            raw = r["raw"]
            if len(raw) < 128:
                n_bad += 1
                continue
            iq = raw[:128].reshape(64, 2).astype(np.float32)        # [imag, real] pairs; LLTF only
            H = (iq[:, 1] + 1j * iq[:, 0]).astype(np.complex64)
            if r["first_word_invalid"]:
                H[0:2] = np.nan
            g = groups[r["mac"]]
            for key in ("t_host", "seq", "rssi", "ts_us", "channel", "noise_floor", "first_word_invalid"):
                g[key].append(r[key])
            g["H"].append(H)
    if not groups:
        raise ValueError(f"No CSI_DATA lines parsed from {path}")
    ts_all = {m: _unwrap_counter(np.asarray(g["ts_us"]), TS_WRAP) for m, g in groups.items()}
    t0_us = min(int(v[0]) for v in ts_all.values())
    th_all = [np.asarray(g["t_host"], float) for g in groups.values()]
    t0_host = float(np.nanmin([np.nanmin(v) for v in th_all])) if np.isfinite(np.nanmin([np.nanmin(v) for v in th_all])) else float("nan")
    links = {}
    for i, mac in enumerate(sorted(groups)):
        g = groups[mac]
        ts = ts_all[mac]
        t = (ts - t0_us) / 1e6
        order = np.argsort(t, kind="stable")
        links[mac] = LinkStream(
            mac=mac,
            t=t[order],
            t_host=(np.asarray(g["t_host"], float) - t0_host)[order],
            seq=_unwrap_counter(np.asarray(g["seq"]), SEQ_WRAP)[order],
            rssi=np.asarray(g["rssi"], np.int16)[order],
            channel=np.asarray(g["channel"], np.int16)[order],
            noise_floor=np.asarray(g["noise_floor"], np.int16)[order],
            first_word_invalid=np.asarray(g["first_word_invalid"], np.int8)[order],
            H=np.stack(g["H"])[order],
            label=f"Sensor {i + 1}",
        )
    duration = max(float(L.t[-1]) for L in links.values())
    return CSISession(path=path, links=links, n_lines=n_lines, n_bad=n_bad,
                      t0_receiver_us=t0_us, t0_host=t0_host, duration_s=duration,
                      lengths_seen=dict(lengths))


# --------------------------------------------------------------------------- #
# 3. Stream health (what the hardware is actually delivering)
# --------------------------------------------------------------------------- #
def link_health(L: LinkStream) -> dict:
    t = L.t
    dt = np.diff(t)
    dseq = np.diff(L.seq)
    lost = int(np.sum(np.clip(dseq - 1, 0, None)))
    sent = int(L.seq[-1] - L.seq[0] + 1)
    amp = np.abs(L.H[:, valid_slots(bool(L.first_word_invalid[0]))])
    m_db = 20 * np.log10(np.sqrt(np.mean(amp ** 2, axis=1)) + 1e-9)
    steps = np.abs(np.diff(m_db)) > 1.5
    host_dt = np.diff(L.t_host) if np.all(np.isfinite(L.t_host)) else np.array([np.nan])
    off = L.t_host - L.t
    off_detr = off - np.polyval(np.polyfit(t, off, 1), t) if np.all(np.isfinite(off)) else np.array([np.nan])
    return {
        "sensor": L.label,
        "mac": L.mac,
        "packets": int(len(t)),
        "duration_s": float(t[-1] - t[0]),
        "rate_hz": float((len(t) - 1) / max(t[-1] - t[0], 1e-9)),
        "median_interval_ms": float(np.median(dt) * 1e3),
        "interval_p95_ms": float(np.percentile(dt, 95) * 1e3),
        "max_gap_ms": float(dt.max() * 1e3),
        "loss_pct": float(100.0 * lost / max(sent, 1)),
        "lost_packets": lost,
        "rssi_mean_dbm": float(np.mean(L.rssi)),
        "rssi_sd_db": float(np.std(L.rssi)),
        "rssi_min_dbm": int(L.rssi.min()),
        "rssi_max_dbm": int(L.rssi.max()),
        "gain_step_pct": float(100.0 * np.mean(steps)),
        "host_interval_sd_ms": float(np.nanstd(host_dt) * 1e3),
        "receiver_interval_sd_ms": float(np.std(dt) * 1e3),
        "host_offset_sd_ms": float(np.nanstd(off_detr) * 1e3),
        "channel": int(np.bincount(L.channel.astype(int)).argmax()),
        "valid_subcarriers": int(len(valid_slots(bool(L.first_word_invalid[0])))),
    }


def session_health(S: CSISession) -> List[dict]:
    return [link_health(S.links[m]) for m in S.macs]


def rolling_rate(L: LinkStream, t_grid: np.ndarray, win_s: float = 5.0) -> np.ndarray:
    """Packets per second in a trailing window, evaluated on ``t_grid``."""
    lo = np.searchsorted(L.t, t_grid - win_s)
    hi = np.searchsorted(L.t, t_grid)
    return (hi - lo) / win_s


# --------------------------------------------------------------------------- #
# 4. Per-packet sanitisation and uniform resampling
# --------------------------------------------------------------------------- #
def sanitize_packets(H: np.ndarray, first_word_invalid: bool = True) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (amplitude_shape, sanitized_phase, rms_amplitude) for valid subcarriers.

    amplitude_shape: |H_k| / RMS_k|H_k|  -> removes per-packet gain (AGC/FFT scale) steps
    sanitized_phase: unwrap across frequency, minus least-squares line -> removes CFO,
                     STO and SFO terms, which are constant/linear in subcarrier index.
    """
    slots = valid_slots(first_word_invalid)
    k = ESP32_SLOT_TO_SUBCARRIER[slots].astype(float)
    Hv = H[:, slots].astype(np.complex128)
    A = np.abs(Hv)
    rms = np.sqrt(np.mean(A ** 2, axis=1)) + 1e-9
    shape = A / rms[:, None]
    ph = np.unwrap(np.angle(Hv), axis=1)
    kc = k - k.mean()
    slope = (ph * kc).sum(axis=1) / (kc ** 2).sum()
    icpt = ph.mean(axis=1)
    ph_s = ph - (slope[:, None] * kc[None, :] + icpt[:, None])
    return shape.astype(np.float32), ph_s.astype(np.float32), rms.astype(np.float32)


def resample_uniform(t: np.ndarray, X: np.ndarray, fs: float, t_start: float, t_end: float,
                     max_gap_s: float = 0.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    tu = np.arange(t_start, t_end, 1.0 / fs)
    Xu = np.empty((len(tu), X.shape[1]), dtype=np.float64)
    for j in range(X.shape[1]):
        Xu[:, j] = np.interp(tu, t, X[:, j])
    idx = np.clip(np.searchsorted(t, tu), 1, len(t) - 1)
    near = np.minimum(np.abs(tu - t[idx - 1]), np.abs(t[idx] - tu))
    return tu, Xu, near > max_gap_s


def hampel_time(X: np.ndarray, win: int = 7, n_sigma: float = 3.0) -> np.ndarray:
    half = win // 2
    Xp = np.pad(X, ((half, half), (0, 0)), mode="edge")
    W = np.lib.stride_tricks.sliding_window_view(Xp, win, axis=0)
    med = np.median(W, axis=-1)
    mad = 1.4826 * np.median(np.abs(W - med[..., None]), axis=-1) + 1e-12
    return np.where(np.abs(X - med) > n_sigma * mad, med, X)


@dataclass
class LinkFeatures:
    label: str
    mac: str
    fs: float
    t: np.ndarray            # uniform grid (s)
    X: np.ndarray            # (T, C) channels: amplitude-shape then sanitized phase
    gap: np.ndarray          # (T,) bool, sample interpolated across a >max_gap hole
    activity: np.ndarray     # (T,) robust motion/activity index
    rms_db: np.ndarray       # (T,) per-packet RMS amplitude in dB (gain steps visible)
    rssi: np.ndarray         # (T,) RSSI resampled


def link_features(L: LinkStream, fs: float = 10.0, t_end: Optional[float] = None) -> LinkFeatures:
    fwi = bool(L.first_word_invalid[0])
    shape, ph, rms = sanitize_packets(L.H, fwi)
    Xraw = np.hstack([shape, ph])
    t_end = float(L.t[-1]) if t_end is None else t_end
    tu, Xu, gap = resample_uniform(L.t, Xraw, fs, float(L.t[0]), t_end)
    Xu = hampel_time(Xu, win=max(5, int(round(0.7 * fs)) | 1))
    rms_db = np.interp(tu, L.t, 20 * np.log10(rms))
    rssi = np.interp(tu, L.t, L.rssi.astype(float))
    # Motion index (two independent cues, each in robust "x session median" units):
    #  (a) RSSI spread over 2 s  - body movement changes total received power by several dB,
    #      breathing changes it by well under 1 dB;
    #  (b) decorrelation of the 1-s-mean amplitude shape vs 1 s earlier - large movements
    #      reshape the multipath profile across all subcarriers at once.
    n = len(tu)
    k = max(2, int(round(fs)))
    c = np.cumsum(np.vstack([np.zeros((1, shape.shape[1])), Xu[:, :shape.shape[1]]]), axis=0)
    idx = np.arange(n)
    lo = np.maximum(0, idx - k + 1)
    means = (c[idx + 1] - c[lo]) / (idx + 1 - lo)[:, None]
    lag = np.vstack([means[:k], means[:-k]])
    a0 = means - means.mean(1, keepdims=True); a1 = lag - lag.mean(1, keepdims=True)
    dec = 1 - (a0 * a1).sum(1) / np.sqrt((a0 ** 2).sum(1) * (a1 ** 2).sum(1) + 1e-12)
    r2 = int(2 * fs)
    cs, cs2 = np.cumsum(np.r_[0, rssi]), np.cumsum(np.r_[0, rssi ** 2])
    lo2 = np.maximum(0, idx - r2 + 1)
    cnt = idx + 1 - lo2
    mu = (cs[idx + 1] - cs[lo2]) / cnt
    rssi_sd = np.sqrt(np.maximum((cs2[idx + 1] - cs2[lo2]) / cnt - mu ** 2, 0))
    rssi_n = rssi_sd / max(np.median(rssi_sd), 0.25)
    dec_n = dec / (np.median(dec) + 1e-9)
    activity = np.maximum(rssi_n / 3.5, dec_n / 25.0)      # > 1  => motion
    return LinkFeatures(L.label, L.mac, fs, tu, Xu, gap, activity, rms_db, rssi)


# --------------------------------------------------------------------------- #
# 5. Respiratory-rate estimation with a signal-quality gate
# --------------------------------------------------------------------------- #
@dataclass
class RRConfig:
    profile: str = "adult"            # adult | child_1_5y | infant_2_12m | newborn_lt2m
    win_s: float = 30.0               # analysis window (RR algorithms typically 30-32 s)
    hop_s: float = 2.0
    fs: float = 10.0
    n_pcs: int = 3
    peak_halfwidth_hz: float = 0.04   # band counted as "the peak" for prominence
    min_prominence: float = 0.50      # fraction of in-band power within the peak (calibrated)
    min_acf: float = 0.35             # autocorrelation peak height (calibrated)
    agree_bpm: float = 2.5            # spectral vs ACF agreement tolerance
    max_gap_frac: float = 0.10
    min_clean_s: float = 16.0         # shortest motion-free stretch analysed after movement
    recent_s: float = 6.0             # v1.3.2 recency check: newest block, at least this long and one breath
    recent_min_ratio: float = 0.45    # newest block amplitude / strongest earlier block (dev files only)

    @property
    def band_hz(self) -> Tuple[float, float]:
        return {
            "adult": (0.10, 0.75),          # 6-45 breaths/min
            "child_1_5y": (0.15, 1.00),     # 9-60
            "infant_2_12m": (0.20, 1.20),   # 12-72
            "newborn_lt2m": (0.25, 1.40),   # 15-84
        }[self.profile]


def _parabolic_peak(y: np.ndarray, i: int) -> float:
    if 0 < i < len(y) - 1:
        a, b, c = y[i - 1], y[i], y[i + 1]
        den = a - 2 * b + c
        if den != 0:
            return float(i + 0.5 * (a - c) / den)
    return float(i)


def _band_sos(cfg: RRConfig, fs: float, lo: Optional[float] = None):
    lo0, hi = cfg.band_hz
    lo = lo0 if lo is None else lo
    return sig.butter(3, [lo * 0.8, min(hi * 1.15, 0.45 * fs)], btype="bandpass", fs=fs, output="sos")


def estimate_window(Xw: np.ndarray, fs: float, cfg: RRConfig) -> dict:
    """Estimate RR on one analysis window of channels (T, C).

    The lowest reportable rate is raised so that at least two breaths fit in the
    window (a 16 s post-movement window cannot resolve 6 breaths/min).
    """
    lo, hi = cfg.band_hz
    lo = max(lo, 2.0 / (len(Xw) / fs))
    Xf = sig.sosfiltfilt(_band_sos(cfg, fs, lo), Xw - Xw.mean(axis=0), axis=0)
    sd = Xf.std(axis=0)
    keep = sd > 1e-9
    Z = Xf[:, keep] / sd[keep]
    U, s, Vt = np.linalg.svd(Z, full_matrices=False)
    nfft = 8192
    f = np.fft.rfftfreq(nfft, 1.0 / fs)
    band = (f >= lo) & (f <= hi)
    win = np.hanning(len(Z))
    best = None
    for c in range(min(cfg.n_pcs, U.shape[1])):
        pc = U[:, c] * s[c]
        P = np.abs(np.fft.rfft(pc * win, nfft)) ** 2
        Pb = P[band]
        i = int(np.argmax(Pb))
        f_pk = f[band][0] + (_parabolic_peak(Pb, i)) * (f[1] - f[0])
        near = np.abs(f[band] - f_pk) <= cfg.peak_halfwidth_hz
        prom = float(Pb[near].sum() / (Pb.sum() + 1e-12))
        cand = dict(pc=c, f_spec=f_pk, prominence=prom, series=pc, explained=float(s[c] ** 2 / np.sum(s ** 2)),
                    weights=Vt[c], keep=keep, sd=sd)
        if best is None or prom > best["prominence"]:
            best = cand
    pc = best["series"] - best["series"].mean()
    ac = np.correlate(pc, pc, mode="full")[len(pc) - 1:]
    ac = ac / (ac[0] + 1e-12)
    lag_lo, lag_hi = int(fs / hi), int(math.ceil(fs / lo))
    lag_hi = min(lag_hi, len(ac) - 2)
    seg = ac[lag_lo:lag_hi + 1]
    pk, _ = sig.find_peaks(seg)
    if len(pk):
        j = pk[np.argmax(seg[pk])]
        lag = lag_lo + _parabolic_peak(seg, j)
        f_acf, acf_h = fs / lag, float(seg[j])
    else:
        f_acf, acf_h = float("nan"), 0.0
    bpm_s, bpm_a = best["f_spec"] * 60, f_acf * 60
    agree = bool(np.isfinite(bpm_a) and abs(bpm_s - bpm_a) <= cfg.agree_bpm)
    return dict(bpm_spec=bpm_s, bpm_acf=bpm_a, prominence=best["prominence"], acf=acf_h,
                agree=agree, pc=best["pc"], waveform=best["series"], Xf=Xf,
                weights=best["weights"], keep=best["keep"], sd=best["sd"])


@dataclass
class RRTrack:
    label: str
    mac: str
    t: np.ndarray            # window end times (s)
    bpm: np.ndarray          # NaN when withheld
    bpm_raw: np.ndarray      # spectral estimate regardless of quality
    prominence: np.ndarray
    acf: np.ndarray
    reliable: np.ndarray     # bool
    motion: np.ndarray       # bool
    quality: np.ndarray      # 0..1 composite
    resp_rms_ratio: np.ndarray  # recent breathing amplitude / personal baseline
    waveform_t: np.ndarray
    waveform: np.ndarray     # respiratory component (concatenated last-hop segments)
    status: List[str] = field(default_factory=list)
    reason: List[str] = field(default_factory=list)
    pause_s: np.ndarray = field(default_factory=lambda: np.array([]))      # time since last breath swing
    base_period: np.ndarray = field(default_factory=lambda: np.array([]))  # baseline breath period (s)
    pause_snr: np.ndarray = field(default_factory=lambda: np.array([]))    # narrowband SNR of the baseline
    pause_est: np.ndarray = field(default_factory=lambda: np.array([]))    # estimated seconds without breathing movement
    recent_ratio: np.ndarray = field(default_factory=lambda: np.array([]))  # newest block / strongest earlier block (v1.3.2)
    recent_low: np.ndarray = field(default_factory=lambda: np.array([], bool))  # breathing not seen in the newest block
    recent_gated: np.ndarray = field(default_factory=lambda: np.array([], bool))  # clear breathing earlier in the window, none in the newest block


class _SwingCounter:
    """Causal breath-movement detector on a 1-D respiratory projection.

    A "swing" is a turn of the signal (peak or trough) confirmed once the signal has
    moved back by at least ``h`` (hysteresis). Normal breathing produces two swings
    per breath; a breathing pause produces none. ``last_t`` is the time of the most
    recent confirmed swing.
    """

    def __init__(self, h: float, t0: float, x0: float):
        self.h = h
        self.last_t = t0
        self.reset(x0)

    def reset(self, x0: float) -> None:
        self.mode = 0          # 0 = undecided, +1 = tracking a maximum, -1 = tracking a minimum
        self.hi = self.lo = x0

    def update(self, t: float, x: float) -> None:
        if self.mode == 0:
            self.hi, self.lo = max(self.hi, x), min(self.lo, x)
            if self.hi - x > self.h:                       # fell from a maximum
                self.last_t, self.mode, self.lo = t, -1, x
            elif x - self.lo > self.h:                     # rose from a minimum
                self.last_t, self.mode, self.hi = t, 1, x
        elif self.mode == 1:
            if x > self.hi:
                self.hi = x
            elif self.hi - x > self.h:                     # peak confirmed
                self.last_t, self.mode, self.lo = t, -1, x
        else:
            if x < self.lo:
                self.lo = x
            elif x - self.lo > self.h:                     # trough confirmed
                self.last_t, self.mode, self.hi = t, 1, x


def _narrowband_amp(p: np.ndarray, fs: float, f0: float, spread_hz: float = 0.05, window: str = "hann") -> float:
    """Largest windowed DFT amplitude of ``p`` within f0 +/- spread (matched to the breathing rate).

    ``window="boxcar"`` weights every sample equally, so after breathing stops the estimate
    falls linearly with the silent fraction of the segment (used by the pause detector).
    """
    n = len(p)
    if n < 4 or not np.isfinite(f0):
        return float("nan")
    w = np.ones(n) if window == "boxcar" else np.hanning(n)
    x = (p - p.mean()) * w
    tt = np.arange(n) / fs
    best = 0.0
    for f in f0 + np.linspace(-spread_hz, spread_hz, 5):
        if f <= 0:
            continue
        best = max(best, float(np.abs(np.sum(x * np.exp(-2j * np.pi * f * tt)))))
    return 2.0 * best / w.sum()


def _recent_ratio(pc: np.ndarray, fs: float, bpm: float, recent_s: float) -> float:
    """Amplitude of the newest block of ``pc`` relative to the strongest earlier block (v1.3.2).

    Blocks are at least ``recent_s`` long and at least one breath at ``bpm``, laid back from the
    window's end. A window can pass the periodicity checks on breaths that ended many seconds ago;
    this ratio says whether breathing is still present now. NaN when fewer than two blocks fit.
    """
    if not np.isfinite(bpm) or bpm <= 0:
        return float("nan")
    n = int(round(max(recent_s, 60.0 / bpm) * fs))
    m = len(pc) // n
    if n < 2 or m < 2:
        return float("nan")
    x = np.asarray(pc[len(pc) - m * n:], float).reshape(m, n)
    rms = np.sqrt(np.mean(x ** 2, axis=1))
    return float(rms[-1] / (rms[:-1].max() + 1e-12))


def track_link(F: LinkFeatures, cfg: RRConfig = RRConfig()) -> RRTrack:
    """Slide a ``win_s`` window every ``hop_s`` and estimate RR, quality and pause time.

    Rate: zero-phase analysis of the trailing window (``estimate_window``).
    Pause: a strictly causal per-sample pass. The channels are band-passed with a
    causal IIR filter and projected onto the respiratory direction learned from
    the most recent *reliable* window (the person's own baseline). Breath swings
    larger than 40% of that baseline's peak-to-peak are counted; ``pause_s`` is the
    time since the last swing. The baseline is discarded after movement, so a
    posture change cannot masquerade as a pause.
    """
    fs = F.fs
    nw, nh = int(cfg.win_s * fs), int(cfg.hop_s * fs)
    n_tail = int(6 * fs)
    thr = 1.0                                   # activity is already in "threshold units"
    k = max(1, int(1 * fs))
    act_s_all = np.convolve(F.activity, np.ones(k) / k, mode="same")
    ends = np.arange(nw, len(F.t) + 1, nh)
    out = defaultdict(list)
    wave_t, wave = [], []
    base = None            # dict(keep, sd, w, amp, period) from last reliable window
    n_min_clean = int(cfg.min_clean_s * fs)
    # causal band-pass of every channel, for the real-time pause detector
    sos_c = _band_sos(cfg, fs)
    x_ref = F.X[: int(5 * fs)].mean(axis=0)
    Xc, _ = sig.sosfilt(sos_c, F.X - x_ref, axis=0,
                        zi=np.zeros((sos_c.shape[0], 2, F.X.shape[1])))
    swing = None
    prev_e = 0
    pause_min = 10.0 if cfg.profile == "adult" else 20.0
    for e in ends:
        s0 = e - nw
        act_s = act_s_all[s0:e]
        moving_now = bool(act_s[-n_tail:].max() > thr)
        hot = np.where(act_s > thr)[0]
        contaminated = False
        if len(hot):
            # adaptive window: after movement, analyse only the clean stretch since it ended
            s_clean = s0 + int(hot[-1]) + int(1 * fs) + 1
            if e - s_clean >= n_min_clean:
                s0 = s_clean
            else:
                contaminated = True
        # --- causal pause tracking over the samples that arrived since the last hop ---
        moved_since = bool((act_s_all[prev_e:e] > thr).any())
        if moved_since:
            base, swing = None, None            # movement: baseline no longer valid
        if base is not None and swing is not None:
            Zc = Xc[prev_e:e][:, base["keep"]] / base["sd"][base["keep"]]
            p = Zc @ base["w"]
            for ti, xi in zip(F.t[prev_e:e], p):
                swing.update(float(ti), float(xi))
            pause_s = float(F.t[e - 1] - swing.last_t)
            # quiet ratio (v1.3.1): breathing-band amplitude over the last need + 10 s, equal weights,
            # relative to the baseline measured the same way. After breathing stops it falls linearly,
            # reaching 1 - need / (need + 10) once the pause has lasted `need` seconds.
            need = max(pause_min, base["period"])
            n_q = int(round((need + 10.0) * fs))
            if e - n_q >= base["start"]:
                seg_q = (Xc[e - n_q:e][:, base["keep"]] / base["sd"][base["keep"]]) @ base["w"]
                quiet = float(_narrowband_amp(seg_q, fs, base["f"], window="boxcar") / (base["nb"] + 1e-12))
            else:
                quiet = float("nan")
        else:
            pause_s, quiet = float("nan"), float("nan")
        prev_e = e
        # --- window-level rate estimate ---
        Xw = F.X[s0:e]
        gap_frac = float(F.gap[s0:e].mean())
        r = estimate_window(Xw, fs, cfg)
        q = float(np.clip(0.5 * (r["prominence"] / 0.6) + 0.5 * (r["acf"] / 0.7), 0, 1))
        periodic = (r["agree"] and r["prominence"] >= cfg.min_prominence and r["acf"] >= cfg.min_acf
                    and not contaminated and gap_frac <= cfg.max_gap_frac)
        # v1.3.2 recency check: a rate is shown only if breathing is still present in the newest block.
        # A window can pass the periodicity checks on breaths that ended many seconds ago.
        rr = _recent_ratio(r["waveform"], fs, r["bpm_spec"], cfg.recent_s)
        recent_low = bool(np.isfinite(rr) and rr < cfg.recent_min_ratio)
        reliable = periodic and not recent_low
        if periodic:   # the pause detector's baseline still learns from every window with clear breathing
            keep, sd, wv = r["keep"], r["sd"], r["weights"]
            pc = (Xc[s0:e][:, keep] / sd[keep]) @ wv
            pc_ss = pc[int(3 * fs):]                       # skip the causal filter's start-up
            win_rms = float(np.std(pc_ss))
            tail_rms = float(np.std(pc[-int(pause_min * fs):]))
            # re-baseline only while breathing is still present at the end of the window,
            # so a pause that has started cannot lower its own reference
            if base is None or tail_rms >= 0.6 * win_rms:
                amp = float(np.sqrt(2.0) * win_rms)        # half peak-to-peak (sinusoid)
                fresh = base is None
                since = e if fresh else base["since"]
                start = s0 if fresh else base["start"]     # first sample known to hold baseline breathing
                f_b = max(r["bpm_spec"], 1.0) / 60.0
                n_ref = int(round((max(pause_min, 1.0 / f_b) + 10.0) * fs))
                ref = pc[-n_ref:]
                nb_sig = _narrowband_amp(ref, fs, f_b, window="boxcar")
                # narrowband noise level of the same projection away from the breathing peak
                lo_b, hi_b = cfg.band_hz
                offs = [f for f in (f_b - 0.30, f_b - 0.20, f_b + 0.20, f_b + 0.30) if lo_b <= f <= hi_b]
                nb_noise = float(np.median([_narrowband_amp(ref, fs, f, 0.0, window="boxcar") for f in offs])) if offs else float("nan")
                base = dict(keep=keep, sd=sd, w=wv, amp=amp, rms=win_rms, since=since, start=start,
                            period=1.0 / f_b, f=f_b, nb=nb_sig,
                            snr_nb=float(nb_sig / (nb_noise + 1e-12)) if np.isfinite(nb_noise) else float("nan"))
                if fresh or swing is None:
                    swing = _SwingCounter(h=0.8 * amp, t0=float(F.t[e - 1]), x0=float(pc[-1]))
                else:
                    # re-express the running detector in the new projection (its sign may flip);
                    # the time of the last confirmed swing is kept
                    swing.h = 0.8 * amp
                    swing.reset(float(pc[-1]))
        w = r["waveform"]
        out["t"].append(F.t[e - 1]); out["bpm_raw"].append(r["bpm_spec"])
        out["bpm"].append(r["bpm_spec"] if reliable else np.nan)
        out["prom"].append(r["prominence"]); out["acf"].append(r["acf"])
        out["rel"].append(reliable); out["mot"].append(moving_now)
        out["q"].append(0.0 if contaminated else q)
        out["pause"].append(pause_s)
        out["quiet"].append(quiet)
        out["snr_nb"].append(base["snr_nb"] if base is not None else np.nan)
        out["period"].append(base["period"] if base is not None else np.nan)
        out["recent"].append(rr); out["recent_low"].append(recent_low); out["gated"].append(periodic and recent_low)
        seg = w[-nh:] / (np.std(w) + 1e-12)
        wave_t.append(F.t[e - nh:e]); wave.append(seg)
    trk = RRTrack(
        label=F.label, mac=F.mac, t=np.asarray(out["t"]), bpm=np.asarray(out["bpm"], float),
        bpm_raw=np.asarray(out["bpm_raw"]), prominence=np.asarray(out["prom"]), acf=np.asarray(out["acf"]),
        reliable=np.asarray(out["rel"], bool), motion=np.asarray(out["mot"], bool),
        quality=np.asarray(out["q"]), resp_rms_ratio=np.asarray(out["quiet"], float),
        waveform_t=np.concatenate(wave_t) if wave_t else np.array([]),
        waveform=np.concatenate(wave) if wave else np.array([]),
    )
    trk.pause_s = np.asarray(out["pause"], float)
    trk.pause_snr = np.asarray(out["snr_nb"], float)
    trk.base_period = np.asarray(out["period"], float)
    trk.recent_ratio = np.asarray(out["recent"], float)
    trk.recent_low = np.asarray(out["recent_low"], bool)
    trk.recent_gated = np.asarray(out["gated"], bool)
    trk.status, trk.reason = screening_flags(trk, cfg)
    return trk


# --------------------------------------------------------------------------- #
# 6. Screening flags (NEWS2 / WHO IMCI informed) with persistence + hysteresis
# --------------------------------------------------------------------------- #
STATUS_ORDER = {"urgent": 3, "watch": 2, "typical": 1, "no_reading": 0, "moving": 0}


def classify_rate(bpm: float, profile: str) -> Tuple[str, str]:
    if not np.isfinite(bpm):
        return "no_reading", "No reliable reading"
    if profile == "adult":
        # NEWS2 respiratory-rate bands: <=8 (3), 9-11 (1), 12-20 (0), 21-24 (2), >=25 (3)
        if bpm <= 8.5:
            return "urgent", "Very slow breathing"
        if bpm < 11.5:
            return "watch", "Slow breathing"
        if bpm <= 20.5:
            return "typical", "Typical breathing rate"
        if bpm < 24.5:
            return "watch", "Fast breathing"
        return "urgent", "Very fast breathing"
    # WHO IMCI fast-breathing thresholds by age band
    cut = {"newborn_lt2m": 60, "infant_2_12m": 50, "child_1_5y": 40}[profile]
    if bpm >= cut:
        return ("urgent" if profile == "newborn_lt2m" else "watch"), f"Fast breathing for age (>= {cut}/min)"
    if bpm < {"newborn_lt2m": 25, "infant_2_12m": 20, "child_1_5y": 15}[profile]:
        return "watch", "Slow breathing for age"
    return "typical", "Typical breathing rate for age"


def screening_flags(trk: RRTrack, cfg: RRConfig, persist_hops: int = 2,
                    pause_min_s: Optional[float] = None, quiet_ratio: Optional[float] = None,
                    min_pause_snr: float = 3.0, no_reading_after_s: float = 20.0,
                    quiet_persist_hops: int = 2, swing_resume_snr: float = 6.0) -> Tuple[List[str], List[str]]:
    """Per-hop status with persistence: a level must hold for ``persist_hops`` hops.

    A breathing pause is flagged when either test says breathing movement has been absent for
    at least ``need`` = max(``pause_min_s``, one baseline breath period); ``pause_min_s`` is 10 s
    for adults and 20 s for children (AASM adult and pediatric apnea durations).

    * Swing test: no confirmed breath swing for ``need`` seconds (exact timing on strong links).
    * Band test (v1.3.1): the breathing-band amplitude over the last ``need`` + 10 s (equal weights)
      has fallen to the level expected once breathing has been absent for ``need`` seconds, given
      the baseline's measured noise floor: q = sqrt((1 - need/(need+10))^2 + (1/SNR)^2). It must hold
      for ``quiet_persist_hops`` hops, needs SNR >= ``min_pause_snr`` and cannot re-trigger until the
      window has cleared a previous pause.

    A pause is only flagged after a confirmed breathing rate was shown within the quiet window (you
    cannot say breathing stopped without having seen it), and movement releases the flag because a
    pause can no longer be measured. Otherwise the flag is immediate and stays latched until breathing
    returns: the band
    amplitude must recover above q + 0.25 (hysteresis), or on strong links (SNR >= ``swing_resume_snr``)
    breath swings must reappear. ``trk.pause_est`` receives the estimated seconds without breathing.
    ``quiet_ratio`` is accepted for backward compatibility and ignored.
    """
    if pause_min_s is None:
        pause_min_s = 10.0 if cfg.profile == "adult" else 20.0
    n = len(trk.t)
    status, reason = [], []
    current, cur_reason = "no_reading", "Warming up (first 30 s)"
    pending, pending_n = None, 0
    last_good_t = -1e9
    smooth: List[float] = []
    pause_latched = False
    pause_label = f"Possible breathing pause (>= {int(pause_min_s)} s)"
    pause_s = trk.pause_s if len(trk.pause_s) == n else np.full(n, np.nan)
    period = trk.base_period if len(trk.base_period) == n else np.full(n, np.nan)
    resumed_until = -1e9
    last_resume = -1e9
    resumed_label = "Breathing resumed after a pause. Please check on them."
    quiet = trk.resp_rms_ratio if len(trk.resp_rms_ratio) == n else np.full(n, np.nan)
    snr = trk.pause_snr if len(trk.pause_snr) == n else np.full(n, np.nan)
    recent_low = trk.recent_low if len(trk.recent_low) == n else np.zeros(n, bool)
    gated = trk.recent_gated if len(trk.recent_gated) == n else np.zeros(n, bool)
    pause_est = np.full(n, np.nan)
    quiet_run, latch_t0, latch_est0 = 0, 0.0, 0.0
    last_rate_t = -1e9           # last hop whose shown status came from a confirmed breathing rate
    for i in range(n):
        t = trk.t[i]
        need = max(pause_min_s, period[i]) if np.isfinite(period[i]) else pause_min_s
        wq = need + 10.0
        no_swing = bool(np.isfinite(pause_s[i]) and pause_s[i] >= need)
        armed = bool(np.isfinite(snr[i]) and snr[i] >= min_pause_snr)
        r_n = 1.0 / snr[i] if armed else float("nan")
        q_thr = float(np.clip(np.hypot(1.0 - need / wq, r_n), 0.3, 0.75)) if armed else float("nan")
        quiet_now = bool(armed and np.isfinite(quiet[i]) and quiet[i] < q_thr and (t - last_resume) >= wq)
        quiet_run = quiet_run + 1 if quiet_now else 0
        band_quiet = quiet_run >= quiet_persist_hops
        tau_band = (float(np.clip(wq * (1.0 - np.sqrt(max(0.0, quiet[i] ** 2 - r_n ** 2))), 0.0, wq))
                    if armed and np.isfinite(quiet[i]) else float("nan"))
        cands = [v for v in (pause_s[i], tau_band) if np.isfinite(v)]
        est = max(cands) if cands else float("nan")
        pause_est[i] = est
        low = no_swing or band_quiet
        # a pause can only follow a confirmed breathing reading shown within the quiet window
        if low and not pause_latched and (t - last_rate_t) <= wq:
            pause_latched = True
            latch_t0, latch_est0 = t, max(est if np.isfinite(est) else need, need)
        if pause_latched and trk.motion[i]:
            pause_latched = False                       # movement: the pause can no longer be measured
            quiet_run = 0
        if pause_latched:
            # latched high-priority state: clears only when breathing movement returns
            if not np.isfinite(pause_s[i]):
                back = bool(trk.reliable[i])            # baseline lost (movement) and a fresh reading
            else:
                band_back = (not armed) or (not np.isfinite(quiet[i])) or quiet[i] > min(0.95, q_thr + 0.25)
                swing_back = bool(np.isfinite(snr[i]) and snr[i] >= swing_resume_snr and np.isfinite(period[i])
                                  and pause_s[i] < 1.5 * period[i])
                back = (not no_swing) and (band_back or swing_back)
            if back:
                pause_latched = False
                resumed_until = t + 30.0
                last_resume = t
                quiet_run = 0
            else:
                lvl, why = "urgent", pause_label
                pause_est[i] = max(est if np.isfinite(est) else 0.0, latch_est0 + (t - latch_t0))
        if not pause_latched:
            if trk.motion[i]:
                lvl, why = "moving", "Movement detected. Reading paused."
            elif trk.reliable[i]:
                smooth = (smooth + [trk.bpm[i]])[-3:]
                lvl, why = classify_rate(float(np.median(smooth)), cfg.profile)
                last_good_t = t
                if t <= resumed_until and STATUS_ORDER[lvl] < STATUS_ORDER["watch"]:
                    lvl, why = "watch", resumed_label
                elif not armed and np.isfinite(snr[i]):
                    why = why + " (pause check limited: weak signal)"
            elif t <= resumed_until:
                lvl, why = "watch", resumed_label
            elif ((t - last_good_t) <= no_reading_after_s and current in ("typical", "watch")
                  and cur_reason != resumed_label and not recent_low[i]):
                lvl, why = current, cur_reason          # hold a rate-based state briefly, unless breathing has gone quiet
            else:
                lvl, why = "no_reading", "No reliable reading. Count breaths for 60 s."
        if lvl == current:
            pending, pending_n = None, 0
            cur_reason = why
        else:
            immediate = (lvl == "urgent" and why == pause_label) or lvl == "moving" or current == "moving"
            if pending == lvl:
                pending_n += 1
            else:
                pending, pending_n = lvl, 1
            if immediate or pending_n >= persist_hops:
                current, cur_reason = lvl, why
                pending, pending_n = None, 0
        status.append(current)
        reason.append(cur_reason)
        # breathing counts as seen when a rate-based state is shown, or when the window held clear
        # breathing that has since gone quiet (v1.3.2: such windows show no rate, but they do show breathing)
        if (current in ("typical", "watch", "urgent") and cur_reason not in (pause_label, resumed_label)) or gated[i]:
            last_rate_t = t
    trk.pause_est = pause_est
    return status, reason


def analyze_session(S: CSISession, cfg: RRConfig = RRConfig(), profiles: Optional[Dict[str, str]] = None) -> Dict[str, RRTrack]:
    tracks = {}
    t_end = min(float(L.t[-1]) for L in S.links.values())
    for mac in S.macs:
        c = cfg if not profiles or mac not in profiles else RRConfig(**{**cfg.__dict__, "profile": profiles[mac]})
        F = link_features(S.links[mac], fs=c.fs, t_end=t_end)
        tracks[mac] = track_link(F, c)
    return tracks


# --------------------------------------------------------------------------- #
# 7. Semi-synthetic injection of known breathing into a real-format log
# --------------------------------------------------------------------------- #
@dataclass
class BreathingScenario:
    """Piecewise breathing truth for one link. ``segments``: (t_start, t_end, bpm); bpm 0 = pause/absent."""
    segments: Sequence[Tuple[float, float, float]]
    depth: float = 0.05            # peak amplitude modulation depth (fraction)
    phase_depth: float = 0.05      # peak phase modulation (rad)
    common_mode: float = 0.3       # fraction of modulation identical on all subcarriers
    rate_jitter: float = 0.04      # relative breath-to-breath rate variability
    seed: int = 0
    name: str = ""

    def bpm_at(self, t: np.ndarray) -> np.ndarray:
        out = np.full_like(np.asarray(t, float), np.nan)
        for a, b, r in self.segments:
            m = (t >= a) & (t < b)
            out[m] = r
        return out


def breathing_waveform(t: np.ndarray, sc: BreathingScenario) -> Tuple[np.ndarray, np.ndarray]:
    """Return (waveform b(t) in [-1, 1]-ish, true instantaneous bpm) on arbitrary times ``t``."""
    rng = np.random.default_rng(sc.seed)
    # fixed internal grid (independent of the query times) so every call reproduces
    # exactly the same realisation of rate variability for a given scenario + seed
    horizon = max(float(b) for _, b, _ in sc.segments) + 5.0
    tg = np.arange(0.0, horizon, 0.05)
    bpm = sc.bpm_at(tg)
    bpm_f = np.nan_to_num(bpm, nan=0.0)
    # smooth transitions between segments (~4 s)
    k = int(4 / 0.05)
    bpm_s = np.convolve(np.pad(bpm_f, (k, k), mode="edge"), np.ones(k) / k, mode="same")[k:-k]
    present = bpm_f > 0
    # slow random rate variability (breath-to-breath)
    walk = np.cumsum(rng.normal(0, 1, len(tg)))
    walk = sig.sosfiltfilt(sig.butter(2, 0.05, fs=20, output="sos"), walk)
    walk = walk / (np.std(walk) + 1e-9) * sc.rate_jitter
    f_inst = (bpm_s / 60.0) * (1 + walk)
    phase = 2 * np.pi * np.cumsum(f_inst) * 0.05
    # inhale/exhale asymmetry + amplitude variability; gate to zero during pauses with soft edges
    wave = np.sin(phase) + 0.25 * np.sin(2 * phase + 0.6)
    amp = 1 + 0.15 * sig.sosfiltfilt(sig.butter(2, 0.03, fs=20, output="sos"), rng.normal(0, 1, len(tg)))
    gate = np.convolve(present.astype(float), np.ones(int(1.5 / 0.05)) / int(1.5 / 0.05), mode="same")
    w = wave * amp * gate
    w = w / (np.percentile(np.abs(w[present]), 95) + 1e-9) if present.any() else w
    true_bpm = np.where(present, f_inst * 60.0, 0.0)          # includes the rate variability
    return np.interp(t, tg, w), np.interp(t, tg, true_bpm)


def inject_breathing(src_csv: str, dst_csv: str, scenarios: Dict[str, BreathingScenario],
                     t_max: Optional[float] = None) -> dict:
    """Write ``dst_csv`` with breathing modulated onto the real packets of ``src_csv``.

    Only the 128 CSI values of each line change; every header field (timestamps,
    sequence numbers, RSSI, flags) is copied verbatim, so loss, jitter and gain
    steps of the real hardware are preserved. Guard/null slots stay zero and the
    corrupt first word is left untouched. Values are re-quantised to int8.
    """
    S = load_csi_session(src_csv)
    t0 = S.t0_receiver_us
    patterns, waves = {}, {}
    for mac, sc in scenarios.items():
        rng = np.random.default_rng(1000 + sc.seed)
        kk = ESP32_SLOT_TO_SUBCARRIER.astype(float) / 26.0
        th1, th2 = rng.uniform(0, 2 * np.pi, 2)
        c1, c2 = rng.uniform(0.6, 1.6, 2)
        diff_a = np.cos(np.pi * c1 * kk + th1)
        diff_p = np.cos(np.pi * c2 * kk + th2)
        patterns[mac] = (sc.common_mode + (1 - sc.common_mode) * diff_a, diff_p)
        tg = np.arange(0.0, S.duration_s + 2.0, 0.01)
        waves[mac] = (tg, breathing_waveform(tg, sc)[0])
    os.makedirs(os.path.dirname(dst_csv) or ".", exist_ok=True)
    data_slots = ESP32_LLTF_DATA_SLOTS
    with open(src_csv, "r", encoding="utf-8", errors="replace") as fin, open(dst_csv, "w", encoding="utf-8") as fout:
        for line in fin:
            r = parse_csi_line(line)
            if r is None or r["mac"] not in scenarios:
                fout.write(line)
                continue
            ts = r["ts_us"]
            t = (ts - t0) / 1e6
            if ts < t0:  # 32-bit wrap
                t = (ts + TS_WRAP - t0) / 1e6
            sc = scenarios[r["mac"]]
            tg, wg = waves[r["mac"]]
            raw = r["raw"].copy()
            iq = raw[:128].reshape(64, 2).astype(np.float64)
            H = iq[:, 1] + 1j * iq[:, 0]
            w_amp, w_ph = patterns[r["mac"]]
            bt = float(np.interp(t, tg, wg))
            mod = np.ones(64, complex)
            mod[data_slots] = (1 + sc.depth * w_amp[data_slots] * bt) * np.exp(1j * sc.phase_depth * w_ph[data_slots] * bt)
            if r["first_word_invalid"]:
                mod[0:2] = 1
            H2 = H * mod
            q = np.empty(128, dtype=np.int64)
            q[0::2] = np.clip(np.round(H2.imag), -127, 127)
            q[1::2] = np.clip(np.round(H2.real), -127, 127)
            if r["first_word_invalid"]:
                q[0:4] = raw[0:4]
            b0 = line.find("["); e0 = line.rfind("]")
            fout.write(line[:b0 + 1] + ",".join(str(int(v)) for v in q) + line[e0:])
    return {"src": src_csv, "dst": dst_csv, "links": list(scenarios)}


def truth_on_grid(sc: BreathingScenario, t: np.ndarray, win_s: float) -> np.ndarray:
    """Mean true bpm over each trailing analysis window (NaN where a pause/absence dominates)."""
    tg = np.arange(0, float(np.max(t)) + 1, 0.05)
    _, bpm = breathing_waveform(tg, sc)
    out = np.empty(len(t))
    for i, te in enumerate(t):
        m = (tg > te - win_s) & (tg <= te)
        seg = bpm[m]
        out[i] = np.nan if np.mean(seg > 0) < 0.8 else float(np.mean(seg[seg > 0]))
    return out
