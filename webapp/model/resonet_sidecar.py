"""ResoNet second opinion for the Hinigram live console.

Reads the receiver's CSI_DATA lines on stdin and keeps the last 75 s of each transmitter's packets.
Every 2 s of a transmitter's own clock it writes one JSON line on stdout: the readings of the six
models of the frozen fallback rule's variant (lin_sync-e80, two seeds x three folds) for the newest
30 s window. Every step is the v1.3.3 bundle's own code, as hinigram_realdata.py runs it on a
recording: hinigram_live.link_features, hinigram_dataset.window_inputs and pca_components, then
hinigram_realdata.model_outputs with each model's calibrated gate (breathing present above 0.5 and
predicted SD at most its tau).

Display only. The console never lets these readings change a status or an alert: in the bundle's
held-out test, letting them fill the rule-based pipeline's gaps gave "no breathing concern" during
6 to 8 of 162 breath-hold windows, against 2 without them (CHANGES.md).

    python resonet_sidecar.py --bundle "<path to Hinigram_v1.3.3>"

Control lines on stdin: ``#profile <mac> <profile>`` and ``#reset``.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from collections import deque

import numpy as np

KEEP_S = 75.0  # as the console's LiveSession keeps
HOP_S = 2.0
TS_WRAP = 2**32
SEEDS, FOLDS = (0, 1), (0, 1, 2)


def emit(**msg: object) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


class Link:
    """One transmitter's recent packets, on the receiver's microsecond clock unwrapped past 2^32."""

    def __init__(self) -> None:
        self.recs: deque = deque()
        self.ts_add = 0
        self.ts_prev: int | None = None
        self.next_t: float | None = None
        self.profile = "adult"

    def add(self, r: dict) -> float:
        ts = r["ts_us"]
        if self.ts_prev is not None and ts - self.ts_prev < -TS_WRAP // 2:
            self.ts_add += TS_WRAP
        self.ts_prev = ts
        t = (ts + self.ts_add) / 1e6
        # [imag, real] pairs, as the bundle reads them
        iq = r["raw"][:128].reshape(64, 2).astype(np.float32)
        h = (iq[:, 1] + 1j * iq[:, 0]).astype(np.complex64)
        if r["first_word_invalid"]:
            h[0:2] = np.nan
        meta = (r["seq"], r["rssi"], r["channel"], r["noise_floor"], r["first_word_invalid"])
        self.recs.append((t, *meta, h))
        while self.recs and self.recs[0][0] < t - KEEP_S:
            self.recs.popleft()
        return t


def stream(hl, mac: str, link: Link):
    """The packets as the bundle's LinkStream, as load_csi_session would build it from a file."""
    recs = sorted(link.recs, key=lambda x: x[0])
    t, seq, rssi, channel, nf, fwi, h = zip(*recs, strict=True)
    t0 = t[0]
    return hl.LinkStream(
        mac=mac,
        t=np.asarray(t, float) - t0,
        t_host=np.full(len(t), np.nan),
        seq=np.asarray(seq, np.int64),
        rssi=np.asarray(rssi, np.int16),
        channel=np.asarray(channel, np.int16),
        noise_floor=np.asarray(nf, np.int16),
        first_word_invalid=np.asarray(fwi, np.int8),
        H=np.stack(h),
        label=mac,
    )


def estimate(hl, hd, rd, variant: str, mac: str, link: Link) -> dict | None:
    """The six models' readings for the newest 30 s window of one transmitter."""
    L = stream(hl, mac, link)
    if L.t[-1] - L.t[0] < hd.WIN_S + 0.5:
        return None
    F = hl.link_features(L, fs=hd.FS)
    ends = hd.window_ends(len(F.t))
    if not len(ends):
        return None
    W = hd.window_inputs(F.X.astype(np.float32), ends[-1:])
    P = hd.pca_components(W, np.array([hd.PROFILES.index(link.profile)]))
    models = []
    for seed in SEEDS:
        for fold in FOLDS:
            m = rd.model_outputs(P, link.profile, variant, seed, fold)
            rate, sd, p = float(m["rate"][0]), float(m["sd"][0]), float(m["p_present"][0])
            shown = bool(p > 0.5 and sd <= m["tau"])
            models.append(dict(seed=seed, fold=fold, rate=rate, sd=sd, p_present=p, shown=shown))
    rates = [x["rate"] for x in models if x["shown"]]
    return dict(
        type="estimate",
        mac=mac,
        t=float(L.t[-1]),
        rate=float(np.median(rates)) if rates else None,
        n_shown=len(rates),
        n_models=len(models),
        p_present=float(np.mean([x["p_present"] for x in models])),
        models=models,
    )


def main() -> int:
    raw = argparse.RawDescriptionHelpFormatter
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=raw)
    ap.add_argument("--bundle", required=True, help="the unzipped Hinigram_v1.3.3 folder")
    a = ap.parse_args()
    bundle = os.path.abspath(a.bundle)
    sys.path[:0] = [bundle, os.path.join(bundle, "training")]
    try:
        import hinigram_dataset as hd
        import hinigram_live as hl
        import hinigram_realdata as rd

        variant = rd.load_rule()["rule"]["variant"]
        warm = np.zeros((1, hd.T_WIN, hd.N_PC), np.float32)
        # load and compile every model once, before the first window needs it
        for seed in SEEDS:
            for fold in FOLDS:
                rd.model_outputs(warm, "adult", variant, seed, fold)
    except Exception as e:  # any failure here means the model is unavailable, said once
        emit(type="error", message=f"The ResoNet models could not be loaded from {bundle}: {e}")
        return 1
    emit(type="ready", variant=variant, n_models=len(SEEDS) * len(FOLDS))

    links: dict[str, Link] = {}
    for line in io.TextIOWrapper(sys.stdin.buffer, encoding="latin-1"):
        if line.startswith("#"):
            parts = line.split()
            if parts[0] == "#reset":
                links.clear()
            elif parts[0] == "#profile" and len(parts) == 3 and parts[2] in hd.PROFILES:
                link = links.setdefault(parts[1].lower(), Link())
                link.profile, link.recs, link.next_t = parts[2], deque(), None
            continue
        r = hl.parse_csi_line(line)
        if r is None or r["len"] != 128 or len(r["raw"]) < 128:
            continue
        link = links.setdefault(r["mac"], Link())
        t = link.add(r)
        if link.next_t is None:
            link.next_t = t + hd.WIN_S + 0.5
        if t < link.next_t:
            continue
        while link.next_t <= t:  # behind after a backlog: one estimate, then back on the 2 s grid
            link.next_t += HOP_S
        try:
            est = estimate(hl, hd, rd, variant, r["mac"], link)
        except Exception as e:  # one bad window must not stop the next
            emit(type="warning", mac=r["mac"], message=str(e))
            continue
        if est:
            emit(**est)
    return 0


if __name__ == "__main__":
    sys.exit(main())
