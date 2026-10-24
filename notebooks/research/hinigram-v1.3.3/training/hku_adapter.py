"""
hku_adapter.py: the HKU AIoT lab Wi-Fi sensing dataset as ESP32 receiver logs
=============================================================================
The dataset (github.com/hku-aiot-courses/lab_wifi_sensing; files from the link in its README) has eight recordings of
34 to 69 s each, made in an office with an Intel AX200 (Wi-Fi 6, 20 MHz at 5.50 GHz, 2 transmit x 2 receive antennas,
245 subcarriers, 100 CSI samples a second), with a PLUX respiration belt giving the breathing rate every second:

* one person at a steady rate (12, 15 and 20 per minute), led by a metronome;
* one person changing rate (12 to 24, 24 to 12, 12 to 24 to 12 per minute);
* two people at once (15 and 20, 15 and 24 per minute), one belt each;
* ``empty.mat``: the same office with nobody in it.

This module writes each recording as a CSV in the ESP32 receiver's own layout, so the frozen v1.3.2
(``hinigram_live.load_csi_session``), the board ("Open a CSV file", and as an injection-bench background) and the learned
models read it without any change. What is kept and what is not:

* Subcarriers: the ESP32 reports 52 LLTF subcarriers 312.5 kHz apart (-26..-1, +1..+26). HE20 tones are 78.125 kHz
  apart, so HE tone 4k sits at exactly the frequency of ESP32 subcarrier k. Those 52 tones go into the ESP32 slot layout
  (slot k for k >= 0, slot 64 + k for k < 0), with the guard and DC slots zero and the first word marked invalid, as the
  original ESP32 reports it. The other 193 tones are dropped.
* Links: each Tx-Rx pair becomes one sensor, MAC 1a:00:00:00:0b:0<1..4>.
* Packet rate: every third sample, about 33 a second (the ESP32 nodes send about 28.5).
* Values: scaled so the median packet RMS is 20, about an ESP32's level, and rounded to int8 like the ESP32's CSI.
* RSSI is not in the dataset; a constant is written, so the movement index uses the change in CSI shape alone.
* Carrier: 5.50 GHz (channel 100), not the ESP32's 2.44 GHz. The dataset states 5.57 GHz, but its subcarrier index
  (-1018..-774, tones of 78.125 kHz) puts the 20 MHz channel 70 MHz lower: most likely the lowest 20 MHz of a 160 MHz band
  centred on 5.57 GHz. The same chest movement changes the path phase about 2.3 times as much as at 2.44 GHz (the
  wavelength is 2.3 times shorter), and the AX200 is a better receiver, so these recordings are likely easier than
  an ESP32 link. Results here test the algorithms on real breathing; they are not ESP32 hardware results.

``trainset.pickle`` is opened with an unpickler that accepts only numpy arrays and plain containers, because a pickle
from elsewhere can otherwise run code when it is loaded.

    python training/hku_adapter.py <folder with trainset.pickle and empty.mat> [out_dir]
writes <out_dir>/hku_<name>.csv for each recording, hku_empty.csv, and hku_reference.json (belt rates, people, files).
"""
from __future__ import annotations

import io
import json
import os
import pickle
import re
import sys
from typing import Dict, List, Optional

import numpy as np

HE_TONE_STEP = 4                                      # 312.5 kHz / 78.125 kHz
ESP_K = [k for k in range(-26, 27) if k != 0]         # the ESP32's 52 LLTF data subcarriers
TARGET_RMS = 20.0
DECIMATE = 3
MAC_FMT = "1a:00:00:00:0b:{:02x}"
EMPTY_S = 120                                         # seconds of the empty office converted
CHANNEL = 100                                         # 5.50 GHz, from the subcarrier index (see above)
RSSI = -50


class SafeUnpickler(pickle.Unpickler):
    """Only numpy arrays, numpy scalars and dtypes, and plain Python containers."""
    ALLOWED = {
        ("numpy", "ndarray"), ("numpy", "dtype"),
        ("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct"),
        ("numpy.core.multiarray", "scalar"), ("numpy._core.multiarray", "scalar"),
        ("numpy.core.numeric", "_frombuffer"), ("numpy._core.numeric", "_frombuffer"),
        ("collections", "OrderedDict"), ("builtins", "complex"), ("builtins", "slice"), ("builtins", "range"),
    }

    def find_class(self, module, name):
        if (module, name) in self.ALLOWED:
            if module.startswith("numpy.core.") and hasattr(np, "_core"):   # numpy 2 renamed numpy.core (and warns on the old name)
                module = "numpy._core." + module[len("numpy.core."):]
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"refusing to load {module}.{name} from the pickle")


def load_trainset(path: str) -> dict:
    with open(path, "rb") as f:
        return SafeUnpickler(f).load()


def tone_numbers(index, n_tones: int, fc: float, bw: float):
    """The HE tone number of each entry along the CSI's subcarrier axis, whatever convention the index is written in
    (as in hku_shrink.py). Returns (convention, tones), or (None, None) when no reading of the index gives the ESP32's tones."""
    esp = {HE_TONE_STEP * k for k in ESP_K}
    try:
        v = np.asarray(index, float).ravel()
    except (TypeError, ValueError):
        v = np.array([])
    cands = []
    if len(v) == n_tones:
        cands += [("tone numbers", v), ("positions from 0", v - (n_tones - 1) / 2), ("positions from 1", v - (n_tones + 1) / 2),
                  ("Hz from the centre", v / bw), ("kHz from the centre", v * 1e3 / bw), ("MHz from the centre", v * 1e6 / bw),
                  ("Hz", (v - fc) / bw), ("MHz", (v * 1e6 - fc) / bw), ("GHz", (v * 1e9 - fc) / bw)]
    if len(v) == n_tones and n_tones % 2 == 0:            # an FFT's bins: 0..n/2-1 then -n/2..-1, or centred on n/2
        cands += [("FFT bin order", np.where(v < n_tones / 2, v, v - n_tones)), ("positions from 0, centre at n/2", v - n_tones // 2)]
    if len(v) == n_tones and n_tones > 1 and np.all(np.diff(v) == 1):   # consecutive tones of a channel off the stated centre
        cands.append(("consecutive tones about a centre %+g tones from the stated carrier" % ((v[0] + v[-1]) / 2), v - (v[0] + v[-1]) / 2))
    if n_tones == 245:                                   # HE20 without an index: tones -122..122 in order
        cands.append(("assumed -122..122 in order", np.arange(n_tones) - 122.0))
    if n_tones == 242:                                   # HE20 data tones without an index: -122..-2, 2..122
        cands.append(("assumed -122..-2, 2..122 in order", np.r_[np.arange(-122, -1), np.arange(2, 123)].astype(float)))
    fits = []
    for name, t in cands:
        if not np.all(np.isfinite(t)):
            continue
        r = np.round(t)
        if np.all(np.abs(t - r) < 0.05) and len(set(r.astype(int)) & esp) >= 48:
            fits.append((name, r.astype(int)))
    # positions from 0 and from 1 can both fit, one tone apart: HE tones run symmetrically about the carrier, so prefer that
    for name, r in fits:
        if r.min() == -r.max():
            return name, r
    return fits[0] if fits else (None, None)


def tone_axis(shape, n_tones: int) -> int:
    """The axis of one recording's CSI that holds the subcarriers (axis 1 unless another axis has the index's length)."""
    if len(shape) > 1 and shape[1] == n_tones:
        return 1
    for a, s in enumerate(shape[1:], start=1):
        if s == n_tones:
            return a
    return 1


def tone_columns(subcarrier_index, n_tones: int, fc: float = np.nan, bw: float = 78125.0):
    """ESP32 subcarrier k -> column of HE tone 4k along the dataset's subcarrier axis, and the index convention found."""
    conv, tones = tone_numbers(subcarrier_index, n_tones, fc, bw)
    if conv is None:
        raw = np.asarray(subcarrier_index).ravel()
        raise ValueError(f"the subcarrier index ({raw.size} values, first {raw[:6].tolist()}) does not give the 52 ESP32 subcarrier "
                         f"frequencies under any convention tried")
    pos = {int(v): i for i, v in enumerate(tones)}
    cols = {k: pos[HE_TONE_STEP * k] for k in ESP_K if HE_TONE_STEP * k in pos}
    return cols, conv


def seconds(ts) -> np.ndarray:
    """Timestamps in seconds. The dataset's are a microsecond counter (about 10,000 a sample at 100 Hz) that can wrap at 2^32."""
    t = np.asarray(ts, float).ravel()
    d = np.diff(t)
    if len(d) and np.median(d) > 0.5:
        t = (t + np.cumsum(np.r_[0, d < -2 ** 31]) * 2.0 ** 32) / 1e6
    return t


def esp32_rows(H: np.ndarray, cols: Dict[int, int], scale: float) -> np.ndarray:
    """H: (n, n_subcarriers) complex for one link -> (n, 128) int8 values in the ESP32 order (imaginary first)."""
    n = H.shape[0]
    slots = np.zeros((n, 64), complex)
    for k, c in cols.items():
        slots[:, k if k > 0 else 64 + k] = H[:, c] * scale
    out = np.empty((n, 128), np.int64)
    out[:, 0::2] = np.clip(np.round(slots.imag), -127, 127)
    out[:, 1::2] = np.clip(np.round(slots.real), -127, 127)
    out[:, 0:4] = 0                                   # first word invalid, as on the original ESP32
    return out


def write_csv(path: str, csi: np.ndarray, ts: np.ndarray, cols: Dict[int, int], host_t0: float, decimate: int = DECIMATE) -> dict:
    """csi: (n, subcarriers, tx, rx) complex; ts: seconds. One sensor per Tx-Rx pair, every third sample
    (decimate=1 for hku_small.npz, which hku_shrink.py has already thinned)."""
    csi = np.asarray(csi)[::decimate]
    if csi.ndim == 3:                                   # the empty office: (n, subcarriers, rx), one transmit antenna
        csi = csi[:, :, None, :]
    ts = seconds(ts)[::decimate]
    ts = ts - ts[0]
    n, _, ntx, nrx = csi.shape
    links = [(a, b) for a in range(ntx) for b in range(nrx)]
    rms = np.sqrt(np.mean(np.abs(csi[:, list(cols.values()), :, :]) ** 2, axis=1))      # (n, tx, rx)
    scales = {L: TARGET_RMS / (np.median(rms[:, L[0], L[1]]) + 1e-12) for L in links}
    rows = {L: esp32_rows(csi[:, :, L[0], L[1]], cols, scales[L]) for L in links}
    if os.path.exists(path):
        sys.exit(f"{path} exists; delete it first (recordings are never overwritten)")
    with open(path, "x", encoding="utf-8") as f:
        for i in range(n):
            ts_us = int(round(100_000_000 + ts[i] * 1e6)) % (2 ** 32)
            for j, L in enumerate(links):
                vals = ",".join(str(int(v)) for v in rows[L][i])
                f.write(f"{host_t0 + ts[i]:.6f},CSI_DATA,{i},{MAC_FMT.format(j + 1)},{RSSI},11,1,0,0,1,1,0,0,0,0,-96,0,{CHANNEL},0,"
                        f"{ts_us},0,47,1,128,1,\"[{vals}]\"\n")
    return {"file": os.path.basename(path), "packets": n * len(links), "links": [MAC_FMT.format(j + 1) for j in range(len(links))],
            "link_names": [f"Tx{a}->Rx{b}" for a, b in links], "duration_s": float(ts[-1]), "rate_hz": float((n - 1) / max(ts[-1], 1e-9))}


def parse_name(name: str) -> dict:
    """breath_bpm12-24_multiperson_ax200_... -> programmed rates and number of people."""
    m = re.search(r"bpm([\d-]+)", name)
    rates = [int(x) for x in m.group(1).split("-")] if m else []
    return {"programmed": rates, "people": 2 if "multiperson" in name else 1, "varied": "multiperson" not in name and len(rates) > 1}


def scalar(x) -> float:
    """One number from a .mat field (scalars load as 1x1 arrays), or NaN when the field is not a single number."""
    try:
        return float(np.ravel(x)[0]) if np.size(x) == 1 else np.nan
    except (TypeError, ValueError):
        return np.nan


def empty_office(data, want, n_tones: int, limit: int):
    """The first `limit` samples of empty.mat shaped like one sample of the recordings, the other fields of each sample
    as numbers (one of them is its timestamp), and the shapes seen. The file mixes packet types (the dataset's lab
    notebook keeps only the (245, 2, 2) ones); with none of the recordings' shape, the commonest shape holding the
    subcarriers is used instead."""
    shapes = {}
    for i, s in enumerate(data):
        sh = tuple(np.shape(s[5]))
        shapes[sh] = shapes.get(sh, 0) + 1
        if sh == want and shapes[sh] == limit:
            break
    scanned = i + 1 if len(data) else 0
    use = want if shapes.get(want) else max((sh for sh in shapes if n_tones in sh), key=shapes.get, default=None)
    if use is None:
        return None, None, use, shapes, scanned
    keep = [s for s in data[:scanned] if tuple(np.shape(s[5])) == use][:limit]
    csi = np.stack([np.asarray(s[5]) for s in keep], axis=0)
    fields = np.array([[scalar(s[f]) for f in range(len(s)) if f != 5] for s in keep], float)
    return csi, fields, use, shapes, scanned


def field_seconds(fields, step_s: float) -> np.ndarray:
    """The empty office's timestamps from its other fields: the first field that counts up, read as a microsecond clock
    when its steps are about a sample apart in microseconds, otherwise rescaled to step_s a sample (the stated 100 Hz)."""
    fields = np.asarray(fields, float).reshape(len(fields), -1)
    ups = []
    for v in fields.T:
        d = np.diff(v)
        if len(d) and np.all(np.isfinite(v)) and np.mean(d > 0) >= 0.99 and np.median(d) > 0:
            ups.append(v)
    for v in ups:                                     # a microsecond clock first (it may wrap at 2^32)
        if 0.2 * step_s * 1e6 <= np.median(np.diff(v)) <= 20 * step_s * 1e6:
            return seconds(v)
    if ups:
        v = ups[0]
        return (v - v[0]) * step_s / np.median(np.diff(v))
    return np.arange(len(fields)) * step_s


def load_empty(path: str, want, n_tones: int):
    """empty.mat: save_experiment[0][i][5] is one CSI sample; the first two minutes shaped like the recordings' samples
    (the recording is hours long and mixes packet types)."""
    import scipy.io
    data = scipy.io.loadmat(path)["save_experiment"][0]
    csi, fields, use, shapes, scanned = empty_office(data, tuple(want), n_tones, EMPTY_S * 100)
    if csi is None:
        print(f"empty.mat: no samples hold the {n_tones} subcarriers (shapes seen: {shapes}); the empty office is skipped")
        return None, None
    print(f"empty.mat: {len(csi)} samples shaped {use} kept, of {scanned} read (shapes seen: {shapes})")
    return csi, field_seconds(fields, 0.01)


def load_small(path: str) -> dict:
    """hku_small.npz from hku_shrink.py, in the same structure as trainset.pickle (already thinned to every third sample)."""
    z = np.load(path, allow_pickle=False)
    if len(z["tones"]) == 0:
        diag = str(z["diagnostics"]) if "diagnostics" in z.files else "(no diagnostics: made by the first hku_shrink.py)"
        sys.exit(f"{path} holds no subcarriers: hku_shrink.py could not read the dataset's subcarrier index. Run the current "
                 f"hku_shrink.py again and send its output. What it found: {diag}")
    n = len(z["names"])
    gts = [[z[k] for k in sorted((k for k in z.files if k.startswith(f"gt{i}_")), key=lambda k: int(k.split("_")[1]))] for i in range(n)]
    c = lambda key: z[key + "_re"].astype(np.float32) + 1j * z[key + "_im"].astype(np.float32)
    return {"ex_name": [str(x) for x in z["names"]], "CSI": [c(f"csi{i}") for i in range(n)], "CSI_timestamp": [z[f"ts{i}"] for i in range(n)],
            "groundtruth": [g if len(g) > 1 else g[0] for g in gts],
            "CSI_info": {"subcarrier_index": z["tones"], "carrier_frequency": z["carrier_frequency"], "subcarrier_bandwidth": z["subcarrier_bandwidth"]},
            "empty": c("csi_empty") if "csi_empty_re" in z.files else None, "thinned": True,
            "empty_fields": z["empty_fields"] if "empty_fields" in z.files else None}


def convert(src: str, out_dir: str) -> dict:
    """src: the folder holding trainset.pickle (and empty.mat), or hku_small.npz, or a folder holding hku_small.npz."""
    small = src if src.endswith(".npz") else os.path.join(src, "hku_small.npz")
    src_dir = src if os.path.isdir(src) else os.path.dirname(src)
    if not (os.path.exists(small) or os.path.exists(os.path.join(src_dir, "trainset.pickle"))):
        sys.exit(f"neither trainset.pickle nor hku_small.npz found at {os.path.abspath(src)}\n\n{__doc__}")
    os.makedirs(out_dir, exist_ok=True)
    ts_all = load_small(small) if os.path.exists(small) and not os.path.exists(os.path.join(src_dir, "trainset.pickle")) else load_trainset(os.path.join(src_dir, "trainset.pickle"))
    dec = 1 if ts_all.get("thinned") else DECIMATE
    info = ts_all["CSI_info"]
    raw = np.asarray(info["subcarrier_index"])
    fc = float(np.ravel(info.get("carrier_frequency", [np.nan]))[0])
    bw = float(np.ravel(info.get("subcarrier_bandwidth", [78125.0]))[0])
    shape0 = np.shape(ts_all["CSI"][0])
    n_tones = raw.size if raw.size in shape0[1:] else shape0[1]
    ax = tone_axis(shape0, n_tones)                     # the subcarriers go on axis 1
    cols, conv = tone_columns(raw, n_tones, fc, bw)
    print(f"subcarrier index read as {conv}: {len(cols)} of the 52 ESP32 frequencies found (axis {ax} of {list(shape0)})")
    ref = {"source": "HKU AIoT lab Wi-Fi sensing dataset (Intel AX200, HE20 at 5.50 GHz, 2x2, 100 Hz; PLUX belt)",
           "conversion": {"subcarriers": "HE tones 4k for ESP32 k = -26..-1, 1..26", "decimate": DECIMATE, "target_rms": TARGET_RMS,
                          "rssi": RSSI, "first_word_invalid": 1, "subcarrier_index_read_as": conv, "esp32_subcarriers_found": len(cols)},
           "recordings": []}
    host0 = 1_700_000_000.0
    for i, (name, csi, ts, gt) in enumerate(zip(ts_all["ex_name"], ts_all["CSI"], ts_all["CSI_timestamp"], ts_all["groundtruth"])):
        name = str(name)
        stem = name[:-4] if name.endswith((".mat", ".pkl", ".csv", ".dat")) else name
        info = parse_name(stem)
        path = os.path.join(out_dir, f"hku_{stem}.csv")
        meta = write_csv(path, np.moveaxis(np.asarray(csi), ax, 1), np.asarray(ts), cols, host0 + 1000 * i, decimate=dec)
        gts = [np.asarray(g, float).ravel().tolist() for g in gt] if isinstance(gt, (list, tuple)) else [np.asarray(gt, float).ravel().tolist()]
        ref["recordings"].append(dict(name=stem, **info, **meta, belt_bpm_per_s=gts))
        print(f"{meta['file']}: {meta['packets']} packets, {meta['duration_s']:.0f} s, {len(gts)} belt series, programmed {info['programmed']}")
    emp = os.path.join(src_dir, "empty.mat")
    if ts_all.get("empty") is not None or os.path.exists(emp):
        if ts_all.get("empty") is not None:
            csi = ts_all["empty"]
            ef = ts_all.get("empty_fields")
            ts = field_seconds(ef, DECIMATE / 100.0) if ef is not None else np.arange(len(csi)) * DECIMATE / 100.0
        else:
            csi, ts = load_empty(emp, shape0[1:], n_tones)
        if csi is not None:
            csi = np.moveaxis(np.asarray(csi), tone_axis(np.shape(csi), n_tones), 1)
            meta = write_csv(os.path.join(out_dir, "hku_empty.csv"), csi, ts, cols, host0 + 9000, decimate=dec)
            ref["empty"] = meta
            print(f"hku_empty.csv: {meta['packets']} packets, {meta['duration_s']:.0f} s (nobody in the office)")
    json.dump(ref, open(os.path.join(out_dir, "hku_reference.json"), "w"), indent=1)
    return ref


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "hku"))
