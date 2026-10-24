"""Shrink the HKU lab dataset to the part Hinigram uses, so it is small enough to attach or e-mail (about 15 MB).

Put this file next to trainset.pickle (and empty.mat, if you have it) and run, with numpy and scipy installed:
    python hku_shrink.py                    (or: python hku_shrink.py <folder with trainset.pickle>)
In a notebook (Colab, Jupyter), paste this file into a cell and run it: it looks in the notebook's current folder; for
files elsewhere, run main("<folder with trainset.pickle>") in the next cell. It writes hku_small.npz: for each recording, the 52 subcarriers at the ESP32's own frequencies (HE tones 4k for
k = -26..-1, 1..26), every third sample (about 33 a second), the timestamps and the belt's breathing rates; and the
first two minutes of the empty office. CSI values are stored as half-precision real and imaginary parts after dividing
by the recording's median magnitude (about three significant digits, still finer than the ESP32's own 8-bit values).

The dataset's subcarrier index can be written several ways (tone numbers, positions from 0 or 1, frequencies); the
script works out which from the index itself and says so. If none fits, it keeps every subcarrier instead (a bigger
file, about 70 MB) and says that too. Either way it prints what it found and stores it in the file, so the conversion
can be checked. hku_adapter.py reads this file as it reads the full one.
"""
import json
import os
import pickle
import sys

import numpy as np

ESP_TONES = [4 * k for k in range(-26, 27) if k != 0]   # HE tone 4k sits at the frequency of ESP32 subcarrier k
DECIMATE = 3
EMPTY_S = 120                                            # seconds of the empty office kept (it is hours long)


class SafeUnpickler(pickle.Unpickler):
    """Only numpy arrays and plain containers: a pickle can otherwise run code when it is opened."""
    ALLOWED = {("numpy", "ndarray"), ("numpy", "dtype"), ("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct"),
               ("numpy.core.multiarray", "scalar"), ("numpy._core.multiarray", "scalar"), ("numpy.core.numeric", "_frombuffer"),
               ("numpy._core.numeric", "_frombuffer"), ("collections", "OrderedDict"), ("builtins", "complex"), ("builtins", "slice"), ("builtins", "range")}

    def find_class(self, module, name):
        if (module, name) in self.ALLOWED:
            if module.startswith("numpy.core.") and hasattr(np, "_core"):   # numpy 2 renamed numpy.core (and warns on the old name)
                module = "numpy._core." + module[len("numpy.core."):]
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"refusing to load {module}.{name} from the pickle")


def half(csi):
    """Complex CSI -> (real, imaginary) float16, scaled so the median magnitude is 1."""
    c = np.asarray(csi)
    c = c / (np.median(np.abs(c)) + 1e-12)
    return c.real.astype(np.float16), c.imag.astype(np.float16)


def tone_numbers(index, n_tones: int, fc: float, bw: float):
    """The HE tone number of each entry along the CSI's subcarrier axis, whatever convention the index is written in.
    Returns (convention, tones), or (None, None) when no reading of the index gives the ESP32's tones."""
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
        if np.all(np.abs(t - r) < 0.05) and len(set(r.astype(int)) & set(ESP_TONES)) >= 48:
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


def main(folder="."):
    if not os.path.exists(os.path.join(folder, "trainset.pickle")):
        sys.exit(f"no trainset.pickle in {os.path.abspath(folder)}\n\n{__doc__}")
    with open(os.path.join(folder, "trainset.pickle"), "rb") as f:
        d = SafeUnpickler(f).load()
    info = d["CSI_info"]
    raw = np.asarray(info.get("subcarrier_index", []))
    fc = float(np.ravel(info.get("carrier_frequency", [np.nan]))[0])
    bw = float(np.ravel(info.get("subcarrier_bandwidth", [np.nan]))[0])
    shape0 = np.shape(d["CSI"][0])
    n_tones = raw.size if raw.size in shape0[1:] else (shape0[1] if len(shape0) > 1 else 0)
    ax = tone_axis(shape0, n_tones)
    conv, tones = tone_numbers(raw, n_tones, fc, bw)
    if conv:
        where = {int(t): i for i, t in enumerate(tones)}
        kept = [t for t in ESP_TONES if t in where]
        cols = [where[t] for t in kept]
    else:
        kept, cols = [], list(range(n_tones))
    diag = {"keys": sorted(map(str, d)), "csi_info_keys": sorted(map(str, info)),
            "subcarrier_index": {"dtype": str(raw.dtype), "shape": list(raw.shape), "first": raw.ravel()[:6].tolist() if raw.size else [],
                                 "last": raw.ravel()[-6:].tolist() if raw.size else []},
            "carrier_frequency": fc, "subcarrier_bandwidth": bw, "csi_shapes": [list(np.shape(c)) for c in d["CSI"]],
            "csi_dtype": str(np.asarray(d["CSI"][0]).dtype), "tone_axis": ax, "n_tones": int(n_tones), "convention": conv,
            "kept_tones": len(cols), "timestamps_first": [float(np.ravel(t)[0]) for t in d["CSI_timestamp"]],
            "timestamp_step": [float(np.median(np.diff(np.ravel(t).astype(float)))) for t in d["CSI_timestamp"]],
            "groundtruth_shapes": [[list(np.shape(x)) for x in (g if isinstance(g, (list, tuple)) else [g])] for g in d["groundtruth"]]}
    out = {"names": np.array([str(n) for n in d["ex_name"]]), "tones": np.array(kept, int),
           "subcarrier_index_raw": raw.astype(float).ravel() if raw.size and raw.dtype.kind in "iuf" else np.array([]),
           "carrier_frequency": np.array(fc), "subcarrier_bandwidth": np.array(bw)}
    for i, (csi, ts, gt) in enumerate(zip(d["CSI"], d["CSI_timestamp"], d["groundtruth"])):
        c = np.moveaxis(np.asarray(csi), ax, 1)[::DECIMATE][:, cols]
        out[f"csi{i}_re"], out[f"csi{i}_im"] = half(c)
        out[f"ts{i}"] = np.asarray(ts, float).ravel()[::DECIMATE]
        gts = gt if isinstance(gt, (list, tuple)) else [gt]
        for j, g in enumerate(gts):                    # two-person recordings have one belt series per person
            out[f"gt{i}_{j}"] = np.asarray(g, float).ravel()
    emp = os.path.join(folder, "empty.mat")
    if os.path.exists(emp):
        import scipy.io
        data = scipy.io.loadmat(emp)["save_experiment"][0]
        csi, fields, use, shapes, scanned = empty_office(data, tuple(shape0[1:]), n_tones, EMPTY_S * 100)   # 100 samples a second
        diag["empty"] = {"entries": len(data), "fields": list(data.dtype.names or []), "scanned": scanned, "kept_shape": use,
                         "kept_entries": 0 if csi is None else len(csi), "shapes_seen": {str(k): v for k, v in shapes.items()},
                         "first_fields": [] if fields is None else np.where(np.isfinite(fields[:5]), fields[:5], None).tolist()}
        if csi is not None:
            eax = tone_axis(csi.shape, n_tones)
            out["csi_empty_re"], out["csi_empty_im"] = half(np.moveaxis(csi, eax, 1)[::DECIMATE][:, cols])
            out["empty_fields"] = fields[::DECIMATE]
    out["diagnostics"] = np.array(json.dumps(diag))
    dst = os.path.join(folder, "hku_small.npz")
    np.savez_compressed(dst, **out)
    print(f"subcarrier index: {raw.size} values, first {diag['subcarrier_index']['first']}, last {diag['subcarrier_index']['last']}")
    print(f"read as: {conv or 'no convention fits: every subcarrier kept'}; {len(cols)} subcarriers kept (axis {ax} of {list(shape0)})")
    if "empty" in diag:
        e = diag["empty"]
        print(f"empty office: {e['kept_entries']} samples shaped {e['kept_shape']} kept, of {e['scanned']} read (shapes seen: {e['shapes_seen']})")
    print(f"wrote {dst}: {os.path.getsize(dst) / 1e6:.1f} MB, {len(d['CSI'])} recordings" + (" + the empty office's first two minutes" if "csi_empty_re" in out else ""))
    if len(cols) == 0:
        print("WARNING: no subcarriers were kept; please send this output as well as the file")


if __name__ == "__main__":
    # in a notebook cell sys.argv holds the kernel's own arguments (-f kernel.json), so only a folder that exists is taken
    folders = [a for a in sys.argv[1:] if os.path.isdir(a)]
    main(*folders[:1])
