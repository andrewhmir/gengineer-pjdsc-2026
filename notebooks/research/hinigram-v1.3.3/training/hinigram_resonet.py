"""
hinigram_resonet.py  (Hinigram v1.3.2, learned breathing-rate estimators in JAX)
===============================================================================
The Resonance Network (RN) of the team's EEG paper, adapted from motor-EEG classification to estimating
breathing rate from ESP32 CSI windows, plus a learned band-power baseline. Every arm shares the same
input, head, loss and training recipe, so a difference between arms comes from the representation.

    drive      I(t) = g * phi(W_enc x(t) + b_enc),  phi(z) = tanh(Re z) + i tanh(Im z)      (paper eq. 1-2)
    lin bank   z_j' = (mu_j + i w_j) z_j + I_j(t), mu_j < 0: a causal damped-sinusoid filter (eq. 8-9, FFT)
    nl bank    z_j' = (mu_j + i w_j) z_j - (b_j + i c_j)|z_j|^2 z_j + sum_k W_jk z_k + I_j(t)   (eq. 3)
               integrated with an exponential Euler step, which is stable for the linear part
    readouts   power      log <|z_j|^2>_t                                   N features       (eq. 6)
               sync       Re and Im of C_jk = <u_j conj(u_k)>_t, j < k       N(N-1) features  (eq. 7)
               surrogate  sync after a fixed circular time shift of each oscillator's phasor series
                          (the paper's control). For narrowband breathing this does NOT destroy phase:
                          a shift s_j turns u_j into u_j exp(-i 2 pi f s_j), so C_jk keeps its magnitude
                          and its angle gains -2 pi f (s_j - s_k), which still encodes the rate
               randphase  sync after an independent random phase rotation of each oscillator in every
                          window: |C_jk| kept exactly, the angle of C_jk destroyed (same 240 features)
    ShallowNet spatial filters -> free 6.4 s FIR filters -> square -> mean -> log: a learned
               log-band-power model with as many features as the power readout
    head       BatchNorm -> Dropout -> [features, age-profile one-hot] -> Dense(64) -> GELU -> Dense(3):
               log-rate mean, log-rate SD (the model's own uncertainty) and a breathing-present logit
    loss       Gaussian NLL on log-rate (windows where breathing fills the window) + BCE on
               breathing present in the newest 6 s (windows where that is unambiguous)
    training   AdamW 1e-3, weight decay 1e-4, cosine schedule, batch 128, at most 40 epochs, early
               stopping on validation loss (patience 8), gradient-norm clipping 1.0 (paper, section III-F,
               with fewer epochs); training and validation use every other window (4 s hop)

A window shows a rate only when the breathing-present probability is above 0.5 and the predicted SD is
below a threshold chosen on validation data (``calibrate``): the learned equivalent of the DSP's gate.
"""
from __future__ import annotations

import glob
import json
import os
import pickle
import sys
import time
from functools import partial

import numpy as np

os.environ.setdefault("XLA_FLAGS", "--xla_force_host_platform_device_count=1")
import jax
import jax.numpy as jnp
import optax

import hinigram_dataset as hd

ARMS = ["lin_power", "lin_sync", "lin_surrogate", "lin_randphase", "nl_power", "nl_sync", "nl_surrogate", "shallow"]
from hinigram_dataset import DEC, T_WIN, DT, SKIP, N_PC, N_OSC, pca_components, pc_cache, surrogate_shifts
HIDDEN, K_FIR = 64, 32
N_PROF = len(hd.PROFILES)
CFG = {"pool": True}                       # True: one shared network per principal component, attention-pooled
IU = np.triu_indices(N_OSC, 1)


def _inv_softplus(y):
    return float(np.log(np.expm1(y)))


# --------------------------------------------------------------------------- parameters
def init(key, arm: str, C: int = None):
    C = (1 if CFG["pool"] else N_PC) if C is None else C
    ks = jax.random.split(key, 8)
    p = {}
    if arm == "shallow":
        p["sp"] = jax.random.normal(ks[0], (C, N_OSC)) / np.sqrt(C)
        p["fir"] = jax.random.normal(ks[1], (K_FIR, N_OSC)) / np.sqrt(K_FIR)
        fdim = N_OSC
    else:
        p["enc_re"] = jax.random.normal(ks[0], (C, N_OSC)) / np.sqrt(C)
        p["enc_im"] = jax.random.normal(ks[1], (C, N_OSC)) / np.sqrt(C)
        p["enc_b"] = jnp.zeros((2, N_OSC))
        p["log_g"] = jnp.zeros(())
        f0 = np.exp(np.linspace(np.log(0.10), np.log(1.40), N_OSC))   # Hz, 6 to 84 breaths/min
        p["w"] = jnp.asarray(2 * np.pi * f0, dtype=jnp.float32)
        p["a_mu"] = jnp.full((N_OSC,), _inv_softplus(0.33), dtype=jnp.float32)   # damping about 0.05 Hz half-bandwidth
        if arm.startswith("nl"):
            p["a_beta"] = jnp.full((N_OSC,), _inv_softplus(0.5), dtype=jnp.float32)
            p["gamma"] = jnp.zeros((N_OSC,))
            p["W_re"] = 0.01 * jax.random.normal(ks[2], (N_OSC, N_OSC))
            p["W_im"] = 0.01 * jax.random.normal(ks[3], (N_OSC, N_OSC))
        fdim = N_OSC if arm.endswith("power") else N_OSC * (N_OSC - 1)        # sync, surrogate, randphase
    p["bn_g"] = jnp.ones(fdim); p["bn_b"] = jnp.zeros(fdim)
    p["W1"] = jax.random.normal(ks[4], (fdim + N_PROF, HIDDEN)) * np.sqrt(2.0 / (fdim + N_PROF))
    p["b1"] = jnp.zeros(HIDDEN)
    p["W2"] = jax.random.normal(ks[5], (HIDDEN, 4)) * 0.01
    p["b2"] = jnp.array([np.log(20.0), -1.0, 0.0, 0.0], dtype=jnp.float32)
    state = {"bn_m": jnp.zeros(fdim), "bn_v": jnp.ones(fdim)}
    return p, state


# --------------------------------------------------------------------------- representation
def drive(p, x):
    pre_re = x @ p["enc_re"] + p["enc_b"][0]
    pre_im = x @ p["enc_im"] + p["enc_b"][1]
    return jnp.exp(p["log_g"]) * (jnp.tanh(pre_re) + 1j * jnp.tanh(pre_im))          # (B, T, N)


def lin_bank(p, I):
    mu = -(jax.nn.softplus(p["a_mu"]) + 0.02)
    lam = mu + 1j * p["w"]
    n = jnp.arange(T_WIN) * DT
    h = jnp.exp(lam[None, :] * n[:, None]) * DT                                          # (T, N)
    L = 1 << int(np.ceil(np.log2(2 * T_WIN)))
    z = jnp.fft.ifft(jnp.fft.fft(I, n=L, axis=1) * jnp.fft.fft(h, n=L, axis=0)[None], axis=1)[:, :T_WIN]
    return z


def nl_bank(p, I):
    mu = -(jax.nn.softplus(p["a_mu"]) + 0.02)
    lam = mu + 1j * p["w"]
    e = jnp.exp(lam * DT)
    phi1 = (e - 1.0) / lam                                                                # exact for the linear part
    beta = jax.nn.softplus(p["a_beta"]) + 1j * p["gamma"]
    W = p["W_re"] + 1j * p["W_im"]

    def step(z, It):
        f = -beta * (jnp.abs(z) ** 2) * z + z @ W.T + It
        z = e * z + phi1 * f
        return z, z

    z0 = jnp.zeros((I.shape[0], N_OSC), dtype=I.dtype)
    _, zs = jax.lax.scan(step, z0, jnp.swapaxes(I, 0, 1))
    return jnp.swapaxes(zs, 0, 1)


def readout(z, arm, shifts, key=None):
    zz = z[:, SKIP:]
    if arm.endswith("power"):
        return jnp.log(jnp.mean(jnp.abs(zz) ** 2, axis=1) + 1e-6)
    u = zz / (jnp.abs(zz) + 1e-6)
    if arm.endswith("randphase"):
        th = jax.random.uniform(key, (u.shape[0], 1, u.shape[2]), maxval=2 * np.pi)
        u = u * jnp.exp(1j * th)
    if arm.endswith("surrogate"):
        n = zz.shape[1]
        idx = (jnp.arange(n)[:, None] - jnp.asarray(shifts)[None, :]) % n                  # (n, N)
        u = jnp.take_along_axis(u, jnp.broadcast_to(idx[None], u.shape), axis=1)
    C = jnp.einsum("btj,btk->bjk", u, jnp.conj(u)) / u.shape[1]
    c = C[:, IU[0], IU[1]]
    return jnp.concatenate([c.real, c.imag], axis=1)


def shallow_feats(p, x):
    s = x @ p["sp"]                                                                       # (B, T, N)
    L = 1 << int(np.ceil(np.log2(T_WIN + K_FIR)))
    y = jnp.fft.irfft(jnp.fft.rfft(s, n=L, axis=1) * jnp.fft.rfft(p["fir"], n=L, axis=0)[None], n=L, axis=1)[:, K_FIR - 1:T_WIN]
    return jnp.log(jnp.mean(y ** 2, axis=1) + 1e-6)


def features(p, x, arm, shifts, key=None):
    if arm == "shallow":
        return shallow_feats(p, x)
    I = drive(p, x)
    z = lin_bank(p, I) if arm.startswith("lin") else nl_bank(p, I)
    return readout(z, arm, shifts, key)


def head(p, s, f, prof, train, key):
    if train:
        m, v = f.mean(0), f.var(0)
        s = {"bn_m": 0.9 * s["bn_m"] + 0.1 * jax.lax.stop_gradient(m), "bn_v": 0.9 * s["bn_v"] + 0.1 * jax.lax.stop_gradient(v)}
    else:
        m, v = s["bn_m"], s["bn_v"]
    h = (f - m) / jnp.sqrt(v + 1e-5) * p["bn_g"] + p["bn_b"]
    if train:
        keep = jax.random.bernoulli(key, 0.7, h.shape)
        h = jnp.where(keep, h / 0.7, 0.0)
    h = jnp.concatenate([h, prof], axis=1)
    h = jax.nn.gelu(h @ p["W1"] + p["b1"])
    o = h @ p["W2"] + p["b2"]
    return o[:, 0], jnp.clip(o[:, 1], -3.5, 1.5), o[:, 2], o[:, 3], s


def forward(p, s, x, prof, arm, shifts, train, key):
    kf = None
    if arm.endswith("randphase"):          # only this arm draws extra randomness, so the other arms' streams are unchanged
        kf, key = jax.random.split(key)
    if not CFG["pool"]:
        mu, ls, pl, _, s = head(p, s, features(p, x, arm, shifts, kf), prof, train, key)
        return mu, ls, pl, s
    # one network shared by every principal component; attention picks the component(s) carrying breathing,
    # the learned counterpart of the DSP choosing the component with the most prominent peak
    B, T, K = x.shape
    xx = jnp.swapaxes(x, 1, 2).reshape(B * K, T, 1)
    mu, ls, pl, att, s = head(p, s, features(p, xx, arm, shifts, kf), jnp.repeat(prof, K, axis=0), train, key)
    a = jax.nn.softmax(att.reshape(B, K), axis=1)
    pool = lambda v: jnp.sum(a * v.reshape(B, K), axis=1)
    return pool(mu), pool(ls), pool(pl), s


def loss_fn(p, s, batch, arm, shifts, train, key):
    mu, ls, pl, s2 = forward(p, s, batch["x"], batch["prof"], arm, shifts, train, key)
    nll = 0.5 * jnp.square((batch["y"] - mu) * jnp.exp(-ls)) + ls
    rl = jnp.sum(nll * batch["my"]) / jnp.maximum(jnp.sum(batch["my"]), 1.0)
    bce = optax.sigmoid_binary_cross_entropy(pl, batch["pres"])
    pll = jnp.sum(bce * batch["mp"]) / jnp.maximum(jnp.sum(batch["mp"]), 1.0)
    return rl + pll, (s2, rl, pll)


# --------------------------------------------------------------------------- data
class Split:
    """All windows of one split and fold, cut on the fly from the cached features."""

    def __init__(self, files, links, every=1, mode="pca"):
        Xs, starts, meta = [], [], []
        off = 0
        for fi, path in enumerate(files):
            d = hd.load_npz(path)
            for li in links:
                L = d["links"][li]
                Xs.append(L["X"])
                ks = np.arange(0, len(L["ends"]), every)
                ends = L["ends"].astype(np.int64)[ks]
                starts.append(off + ends - hd.NW)
                n = len(ends)
                meta.append(dict(file=np.full(n, fi), link=np.full(n, li), k=ks, rate=L["rate"][ks].astype(np.float32),
                                 present=L["present"][ks].astype(np.int8), prof=np.full(n, hd.PROFILES.index(L["profile"]))))
                off += len(L["X"])
        self.X = np.concatenate(Xs).astype(np.float32)
        self.start = np.concatenate(starts)
        self.meta = {k: np.concatenate([m[k] for m in meta]) for k in meta[0]}
        self.files = list(files)
        self.mode = mode
        self.n = len(self.start)
        self.B = hd._detrend_basis(T_WIN)
        if mode == "pca":                       # preprocessing done once per file and cached: each window's top components
            parts = []
            for fi, path in enumerate(files):
                pcs = pc_cache(path)
                for li in links:
                    parts.append(pcs[li][np.arange(0, len(pcs[li]), every)])
            self.P = np.concatenate(parts).astype(np.float32)
            assert len(self.P) == self.n

    def _windows(self, idx):
        W = self.X[self.start[idx][:, None] + np.arange(hd.NW)[None, :]]
        W = W.reshape(len(idx), T_WIN, DEC, W.shape[2]).mean(axis=2)          # 10 Hz -> 5 Hz
        W = W - np.einsum("tk,nkc->ntc", self.B, np.einsum("tk,ntc->nkc", self.B, W))
        sd = W.std(axis=1, keepdims=True)
        W = np.where(sd > 1e-6, W / np.maximum(sd, 1e-6), 0.0)
        return np.clip(W, -5, 5).astype(np.float32)

    def batch(self, idx, augment=False, rng=None):
        if self.mode == "pca":
            W = self.P[idx].copy()
            if augment:
                W = W + rng.normal(0, 0.05, W.shape).astype(np.float32)
                W = W * rng.choice([-1.0, 1.0], size=(len(idx), 1, W.shape[2])).astype(np.float32)   # PCA sign is arbitrary
            return self._pack(idx, W)
        W = self.X[self.start[idx][:, None] + np.arange(hd.NW)[None, :]]
        W = W.reshape(len(idx), T_WIN, DEC, W.shape[2]).mean(axis=2)          # 10 Hz -> 5 Hz
        W = W - np.einsum("tk,nkc->ntc", self.B, np.einsum("tk,ntc->nkc", self.B, W))
        sd = W.std(axis=1, keepdims=True)
        W = np.where(sd > 1e-6, W / np.maximum(sd, 1e-6), 0.0)
        W = np.clip(W, -5, 5).astype(np.float32)
        if augment:
            W = W + rng.normal(0, 0.05, W.shape).astype(np.float32)
            W = W * (rng.random((len(idx), 1, W.shape[2])) > 0.1).astype(np.float32)
        return self._pack(idx, W)

    def _pack(self, idx, W):
        rate = self.meta["rate"][idx]
        my = np.isfinite(rate).astype(np.float32)
        pres = self.meta["present"][idx]
        return dict(x=W, prof=np.eye(N_PROF, dtype=np.float32)[self.meta["prof"][idx]],
                    y=np.where(my > 0, np.log(np.where(my > 0, rate, 1.0)), 0.0).astype(np.float32), my=my,
                    pres=(pres == 1).astype(np.float32), mp=(pres >= 0).astype(np.float32))


def split_files(kind):
    return sorted(glob.glob(os.path.join(hd.HERE, "mldata", kind, "*.npz")))


# --------------------------------------------------------------------------- training
def _prefetch(gen, depth=3):
    """Prepare the next batches in a thread while JAX trains on the current one."""
    import queue, threading
    q, done = queue.Queue(depth), object()

    def work():
        for item in gen:
            q.put(item)
        q.put(done)

    threading.Thread(target=work, daemon=True).start()
    while True:
        item = q.get()
        if item is done:
            return
        yield item


def train(arm, fold, seed, epochs=40, batch=128, lr=1e-3, wd=1e-4, patience=8, log=print, max_train_files=None):
    links_tr = [l for l in range(3) if l != fold]
    tr_files = split_files("train")[:max_train_files] if max_train_files else split_files("train")
    tr, va = Split(tr_files, links_tr, every=2), Split(split_files("val"), links_tr, every=2)
    shifts = surrogate_shifts(seed)
    p, s = init(jax.random.PRNGKey(seed), arm)
    spe = int(np.ceil(tr.n / batch))
    opt = optax.chain(optax.clip_by_global_norm(1.0), optax.adamw(optax.cosine_decay_schedule(lr, epochs * spe), weight_decay=wd))
    o = opt.init(p)

    @jax.jit
    def step(p, s, o, b, key):
        (l, (s2, rl, pl)), g = jax.value_and_grad(loss_fn, has_aux=True)(p, s, b, arm, shifts, True, key)
        upd, o2 = opt.update(g, o, p)
        return optax.apply_updates(p, upd), s2, o2, l, rl, pl

    @jax.jit
    def evaluate(p, s, b, k):
        l, (_, rl, pl) = loss_fn(p, s, b, arm, shifts, False, k)
        return l, rl, pl

    rng = np.random.default_rng(seed)
    key = jax.random.PRNGKey(1000 + seed)
    best, best_p, best_s, wait, hist = np.inf, p, s, 0, []
    t0 = time.time()
    for ep in range(epochs):
        perm = rng.permutation(tr.n)
        brng = np.random.default_rng(rng.integers(1 << 31))
        batches = (tr.batch(perm[i * batch:(i + 1) * batch], augment=True, rng=brng) for i in range(spe) if len(perm[i * batch:(i + 1) * batch]) >= 8)
        tl = []
        for b in _prefetch(batches):
            key, sk = jax.random.split(key)
            p, s, o, l, rl, pl = step(p, s, o, b, sk)
            tl.append(l)
        tl = [float(x) for x in tl]
        vl = []
        for i in range(0, va.n, 512):
            idx = np.arange(i, min(va.n, i + 512))
            l, rl, pl = evaluate(p, s, va.batch(idx), jax.random.fold_in(jax.random.PRNGKey(7), i))
            vl.append((float(l), len(idx)))
        v = sum(a * n for a, n in vl) / sum(n for _, n in vl)
        hist.append(dict(epoch=ep + 1, train=float(np.mean(tl)), val=v, sec=time.time() - t0))
        log(f"{arm} fold{fold} seed{seed} epoch {ep + 1}: train {np.mean(tl):.3f} val {v:.3f} ({time.time() - t0:.0f}s)")
        if v < best - 1e-4:
            best, best_p, best_s, wait = v, p, s, 0
        else:
            wait += 1
            if wait >= patience:
                break
    return best_p, best_s, shifts, hist


def predict(p, s, arm, shifts, split: Split, bs=512):
    f = jax.jit(lambda p, s, x, prof, k: forward(p, s, x, prof, arm, shifts, False, k)[:3])
    mu, ls, pl = [], [], []
    for i in range(0, split.n, bs):
        idx = np.arange(i, min(split.n, i + bs))
        b = split.batch(idx)
        a, c, d = f(p, s, b["x"], b["prof"], jax.random.fold_in(jax.random.PRNGKey(7), i))
        mu.append(np.asarray(a)); ls.append(np.asarray(c)); pl.append(np.asarray(d))
    return dict(rate=np.exp(np.concatenate(mu)), sd=np.exp(np.concatenate(ls)), p_present=1 / (1 + np.exp(-np.concatenate(pl))))


def calibrate(pred, rate_true, target=0.95, tol=2.0):
    """Largest coverage whose accepted validation windows are within +/-tol breaths/min at least `target` of the time."""
    ok = np.isfinite(rate_true) & (pred["p_present"] > 0.5)
    err = np.abs(pred["rate"] - rate_true)
    sd = pred["sd"]
    cand = np.unique(np.quantile(sd[ok], np.linspace(0.01, 1.0, 200))) if ok.any() else np.array([0.0])
    best = (float("-inf"), 0.0, np.nan)          # no threshold reaches the target: the arm never shows a rate
    n_def = int(np.isfinite(rate_true).sum())
    for tau in cand:
        acc = ok & (sd <= tau)
        if acc.sum() < 20:
            continue
        a = float(np.mean(err[acc] <= tol))
        cov = acc.sum() / max(n_def, 1)
        if a >= target and cov > best[1]:
            best = (float(tau), float(cov), a)
    return dict(tau=best[0], val_coverage=best[1], val_within=best[2])


def run(arm, fold, seed, out_dir, suffix="", **kw):
    """suffix names a variant of an arm (for example "-e80" for the 80-epoch schedule), so its files never replace the arm's."""
    os.makedirs(out_dir, exist_ok=True)
    tag = f"{arm}{suffix}{'' if CFG['pool'] else '-p0'}_f{fold}_s{seed}"
    logf = open(os.path.join(out_dir, tag + ".log"), "w")
    log = lambda m: (print(m, flush=True), logf.write(m + "\n"), logf.flush())
    p, s, shifts, hist = train(arm, fold, seed, log=log, **kw)
    links_tr = [l for l in range(3) if l != fold]
    va = Split(split_files("val"), links_tr, every=2)
    pv = predict(p, s, arm, shifts, va)
    cal = calibrate(pv, va.meta["rate"])
    te = Split(split_files("test5"), [fold])
    pt = predict(p, s, arm, shifts, te)
    rw = Split(split_files("raw"), [fold])
    pr = predict(p, s, arm, shifts, rw)
    np.savez_compressed(os.path.join(out_dir, tag + "_pred.npz"),
                        **{f"test_{k}": v for k, v in pt.items()}, **{f"raw_{k}": v for k, v in pr.items()},
                        **{f"val_{k}": v for k, v in pv.items()},
                        test_file=te.meta["file"], test_link=te.meta["link"], test_k=te.meta["k"],
                        raw_file=rw.meta["file"], raw_link=rw.meta["link"], raw_k=rw.meta["k"])
    with open(os.path.join(out_dir, tag + "_params.pkl"), "wb") as fh:
        pickle.dump(dict(params=jax.tree_util.tree_map(np.asarray, p), state=jax.tree_util.tree_map(np.asarray, s),
                         shifts=shifts, arm=arm, fold=fold, seed=seed), fh)
    json.dump(dict(arm=arm + suffix + ("" if CFG["pool"] else "-p0"), base_arm=arm, fold=fold, seed=seed, pool=CFG["pool"], hist=hist, calibration=cal,
                   schedule=dict(epochs=kw.get("epochs", 40), patience=kw.get("patience", 8)), test_files=[os.path.basename(f) for f in te.files]),
              open(os.path.join(out_dir, tag + "_summary.json"), "w"), indent=1)
    log(f"{tag}: calibration {cal}")
    logf.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=ARMS)
    ap.add_argument("--fold", type=int, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--out", default=os.path.join(hd.HERE, "mlruns"))
    ap.add_argument("--max-train-files", type=int, default=None)
    ap.add_argument("--pool", type=int, default=1)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--suffix", default="", help='variant name added to the arm in every file name, e.g. "-e80"')
    a = ap.parse_args()
    CFG["pool"] = bool(a.pool)
    run(a.arm, a.fold, a.seed, a.out, suffix=a.suffix, epochs=a.epochs, patience=a.patience, max_train_files=a.max_train_files)
