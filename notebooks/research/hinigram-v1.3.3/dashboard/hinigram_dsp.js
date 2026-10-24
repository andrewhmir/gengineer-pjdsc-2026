/* Hinigram v1.3.2 in-browser DSP. A line-by-line port of hinigram_live.py
 * (format-faithful ESP32 CSI_DATA parsing, receiver-clock resampling, per-packet gain
 * and phase sanitisation, quality-gated respiratory-rate estimation, causal pause
 * detection and NEWS2 / WHO IMCI screening flags). No dependencies.
 */
(function (root) {
  'use strict';

  // ------------------------------------------------------------------ constants
  const SLOT_TO_SC = new Int16Array(64);
  for (let k = 0; k < 64; k++) SLOT_TO_SC[k] = k < 32 ? k : k - 64;
  const LLTF_DATA_SLOTS = [];
  for (let k = 1; k <= 26; k++) LLTF_DATA_SLOTS.push(k);
  for (let k = 38; k <= 63; k++) LLTF_DATA_SLOTS.push(k);
  const TS_WRAP = 4294967296, SEQ_WRAP = 65536;

  function validSlots(fwi) {
    let s = LLTF_DATA_SLOTS.slice();
    if (fwi) s = s.filter((k) => k >= 2);
    s.sort((a, b) => SLOT_TO_SC[a] - SLOT_TO_SC[b]);
    return s;
  }

  const PROFILES = {
    adult: { band: [0.10, 0.75], label: 'Adult' },
    child_1_5y: { band: [0.15, 1.00], label: 'Child 1 to 5 years' },
    infant_2_12m: { band: [0.20, 1.20], label: 'Infant 2 to 12 months' },
    newborn_lt2m: { band: [0.25, 1.40], label: 'Newborn under 2 months' },
  };

  function defaultConfig(profile) {
    return {
      profile: profile || 'adult', win_s: 30, hop_s: 2, fs: 10, n_pcs: 3,
      peak_halfwidth_hz: 0.04, min_prominence: 0.5, min_acf: 0.35, agree_bpm: 2.5,
      max_gap_frac: 0.10, min_clean_s: 16, recent_s: 6, recent_min_ratio: 0.45,
    };
  }

  // ------------------------------------------------------------------ parsing
  function parseLine(line) {
    const s = line.trim();
    if (s.indexOf('CSI_DATA') < 0) return null;
    const b = s.indexOf('['), e = s.lastIndexOf(']');
    if (b < 0 || e < b) return null;
    // fields are comma-separated as the receiver prints them; tabs or semicolons (a log re-saved from a spreadsheet) work too
    const hdr = s.slice(0, b).replace(/"/g, '').replace(/[,\t;\s]+$/, '').split(/[,\t;]/).map((x) => x.trim());
    const k = hdr.indexOf('CSI_DATA');
    if (k < 0 || hdr.length < k + 24) return null;
    const vals = s.slice(b + 1, e).split(',');
    if (vals.length < 128) return null;
    const raw = new Int16Array(128);
    for (let i = 0; i < 128; i++) {
      const v = parseInt(vals[i], 10);
      if (Number.isNaN(v)) return null;
      raw[i] = v;
    }
    const rec = {
      t_host: k > 0 ? parseFloat(hdr[0]) : NaN,
      seq: parseInt(hdr[k + 1], 10), mac: hdr[k + 2].toLowerCase(), rssi: parseInt(hdr[k + 3], 10),
      noise_floor: parseInt(hdr[k + 14], 10), channel: parseInt(hdr[k + 16], 10),
      ts_us: parseInt(hdr[k + 18], 10), sig_len: parseInt(hdr[k + 20], 10), rx_state: parseInt(hdr[k + 21], 10),
      len: parseInt(hdr[k + 22], 10), fwi: parseInt(hdr[k + 23], 10) === 1, raw: raw,
    };
    if ([rec.seq, rec.rssi, rec.ts_us, rec.len].some((v) => Number.isNaN(v))) return null;
    return rec;
  }

  function unwrapCounter(arr, wrap) {
    const out = new Float64Array(arr.length);
    let add = 0;
    for (let i = 0; i < arr.length; i++) {
      if (i > 0 && arr[i] - arr[i - 1] < -wrap / 2) add += wrap;
      out[i] = arr[i] + add;
    }
    return out;
  }

  /** Build per-MAC link streams from parsed records (any order). */
  function buildSession(records, name) {
    const groups = new Map();
    let nBad = 0;
    for (const r of records) {
      if (!r || r.len !== 128) { nBad++; continue; }
      if (!groups.has(r.mac)) groups.set(r.mac, []);
      groups.get(r.mac).push(r);
    }
    const macs = Array.from(groups.keys()).sort();
    if (!macs.length) throw new Error('No CSI_DATA lines found. Check that the file comes from the ESP32 logger.');
    const tsUn = {};
    let t0 = Infinity, t0h = Infinity;
    for (const m of macs) {
      const g = groups.get(m);
      tsUn[m] = unwrapCounter(g.map((r) => r.ts_us), TS_WRAP);
      t0 = Math.min(t0, tsUn[m][0]);
      for (const r of g) if (Number.isFinite(r.t_host)) t0h = Math.min(t0h, r.t_host);
    }
    const links = {};
    macs.forEach((m, idx) => {
      const g = groups.get(m);
      const n = g.length;
      const order = Array.from({ length: n }, (_, i) => i).sort((a, b) => (tsUn[m][a] - tsUn[m][b]) || (a - b));
      const t = new Float64Array(n), th = new Float64Array(n), rssi = new Float64Array(n);
      const seqRaw = g.map((r) => r.seq);
      const seqUn = unwrapCounter(seqRaw, SEQ_WRAP);
      const seq = new Float64Array(n), H = new Array(n);
      for (let i = 0; i < n; i++) {
        const j = order[i], r = g[j];
        t[i] = (tsUn[m][j] - t0) / 1e6;
        th[i] = Number.isFinite(r.t_host) ? r.t_host - t0h : NaN;
        rssi[i] = r.rssi;
        seq[i] = seqUn[j];
        const re = new Float64Array(64), im = new Float64Array(64);
        for (let s = 0; s < 64; s++) { im[s] = r.raw[2 * s]; re[s] = r.raw[2 * s + 1]; }
        if (r.fwi) { re[0] = re[1] = NaN; im[0] = im[1] = NaN; }
        H[i] = { re, im };
      }
      links[m] = {
        mac: m, label: 'Sensor ' + (idx + 1), t, t_host: th, seq, rssi, H,
        channel: g[0].channel, fwi: g[order[0]].fwi,
      };
    });
    let duration = 0;
    for (const m of macs) duration = Math.max(duration, links[m].t[links[m].t.length - 1]);
    return { name: name || '', links, macs, nBad, duration, t0Host: Number.isFinite(t0h) ? t0h : NaN };
  }

  function parseText(text, name) {
    const lines = text.split(/\r?\n/);
    const recs = [];
    let bad = 0;
    for (const ln of lines) {
      if (!ln.trim()) continue;
      const r = parseLine(ln);
      if (r) recs.push(r); else bad++;
    }
    const S = buildSession(recs, name);
    S.nBad += bad;
    S.nLines = recs.length + bad;
    return S;
  }

  // ------------------------------------------------------------------ small numerics
  const fround = Math.fround;
  function mean(a, lo, hi) { lo = lo || 0; hi = hi === undefined ? a.length : hi; let s = 0; for (let i = lo; i < hi; i++) s += a[i]; return s / (hi - lo); }
  function stdPop(a, lo, hi) { lo = lo || 0; hi = hi === undefined ? a.length : hi; const m = mean(a, lo, hi); let s = 0; for (let i = lo; i < hi; i++) { const d = a[i] - m; s += d * d; } return Math.sqrt(s / (hi - lo)); }
  function median(arr) {
    const a = Array.from(arr).filter((v) => !Number.isNaN(v)).sort((x, y) => x - y);
    const n = a.length; if (!n) return NaN;
    return n % 2 ? a[(n - 1) / 2] : 0.5 * (a[n / 2 - 1] + a[n / 2]);
  }
  function roundHalfEven(x) { const r = Math.round(x); return (Math.abs(x % 1) === 0.5 && r % 2 !== 0) ? r - 1 : r; }
  function hanning(n) { const w = new Float64Array(n); if (n === 1) { w[0] = 1; return w; } for (let i = 0; i < n; i++) w[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1)); return w; }
  function interp1(x, xp, fp) {
    // numpy.interp for sorted xp, scalar x
    const n = xp.length;
    if (x <= xp[0]) return fp[0];
    if (x >= xp[n - 1]) return fp[n - 1];
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (xp[mid] <= x) lo = mid; else hi = mid; }
    const dx = xp[hi] - xp[lo];
    if (dx === 0) return fp[hi];
    return fp[lo] + (fp[hi] - fp[lo]) * (x - xp[lo]) / dx;
  }
  function searchsortedLeft(a, x) { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < x) lo = m + 1; else hi = m; } return lo; }

  // complex helpers
  const C = {
    add: (a, b) => [a[0] + b[0], a[1] + b[1]], sub: (a, b) => [a[0] - b[0], a[1] - b[1]],
    mul: (a, b) => [a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]],
    div: (a, b) => { const d = b[0] * b[0] + b[1] * b[1]; return [(a[0] * b[0] + a[1] * b[1]) / d, (a[1] * b[0] - a[0] * b[1]) / d]; },
    sqrt: (a) => { const r = Math.hypot(a[0], a[1]); let re = Math.sqrt((r + a[0]) / 2), im = Math.sqrt(Math.max(0, (r - a[0]) / 2)); if (a[1] < 0) im = -im; return [re, im]; },
    scale: (a, s) => [a[0] * s, a[1] * s],
  };

  // ------------------------------------------------------------------ Butterworth band-pass (N = 3), scipy-equivalent
  function butterBandpassSOS(lo, hi, fs) {
    const N = 3, fsd = 2.0;
    const w1 = 2 * fsd * Math.tan(Math.PI * (2 * lo / fs) / fsd);
    const w2 = 2 * fsd * Math.tan(Math.PI * (2 * hi / fs) / fsd);
    const bw = w2 - w1, wo = Math.sqrt(w1 * w2);
    const m = [-2, 0, 2];
    const pAn = m.map((mm) => C.scale([Math.cos(Math.PI * mm / (2 * N)), Math.sin(Math.PI * mm / (2 * N))], -1));
    // lp -> bp
    const pBp = [];
    for (const p of pAn) {
      const pl = C.scale(p, bw / 2);
      const root = C.sqrt(C.sub(C.mul(pl, pl), [wo * wo, 0]));
      pBp.push(C.add(pl, root));
    }
    for (const p of pAn) {
      const pl = C.scale(p, bw / 2);
      const root = C.sqrt(C.sub(C.mul(pl, pl), [wo * wo, 0]));
      pBp.push(C.sub(pl, root));
    }
    let kBp = Math.pow(bw, N);
    // bilinear: zeros at s=0 (3) -> z=+1 ; degree 3 extra zeros at z=-1
    const fs2 = 2 * fsd;
    const pZ = pBp.map((p) => C.div(C.add([fs2, 0], p), C.sub([fs2, 0], p)));
    // k_z = k * real(prod(fs2 - z) / prod(fs2 - p)); z (analog) = three zeros at 0
    let num = [Math.pow(fs2, N), 0];
    let den = [1, 0];
    for (const p of pBp) den = C.mul(den, C.sub([fs2, 0], p));
    const kZ = kBp * C.div(num, den)[0];
    // group poles into second-order sections: conjugate pairs, plus a pair of real poles
    const tol = 1e-9;
    const cplx = pZ.filter((p) => p[1] > tol).map((p) => ({ a1: -2 * p[0], a2: p[0] * p[0] + p[1] * p[1], r2: p[0] * p[0] + p[1] * p[1], real: false }));
    const reals = pZ.filter((p) => Math.abs(p[1]) <= tol).map((p) => p[0]).sort((a, b) => a - b);
    const groups = cplx.slice();
    for (let i = 0; i + 1 < reals.length; i += 2) {
      groups.push({ a1: -(reals[i] + reals[i + 1]), a2: reals[i] * reals[i + 1], r2: Math.max(reals[i] * reals[i], reals[i + 1] * reals[i + 1]), real: true });
    }
    if (groups.length !== 3) throw new Error('unexpected pole layout');
    // same section layout as scipy.signal.butter(..., output="sos") for these bands:
    // last = complex pair nearest the unit circle with zeros (+1, +1); a real-pole pair (if any)
    // sits in the middle with zeros (+1, -1); the remaining pair goes first with the gain and zeros (-1, -1)
    const cp = groups.filter((g) => !g.real).sort((x, y) => y.r2 - x.r2);
    const rp = groups.filter((g) => g.real);
    let first, middle, last;
    if (rp.length === 1) { last = cp[0]; first = cp[1]; middle = rp[0]; }
    else { const all = groups.slice().sort((x, y) => y.r2 - x.r2); last = all[0]; first = all[1]; middle = all[2]; }
    return [
      [kZ, 2 * kZ, kZ, 1, first.a1, first.a2],
      [1, 0, -1, 1, middle.a1, middle.a2],
      [1, -2, 1, 1, last.a1, last.a2],
    ];
  }

  function lfilterZi2(b0, b1, b2, a1, a2) {
    // solve (I - companion(a).T) zi = b[1:] - a[1:]*b0  (2x2)
    const B0 = b1 - a1 * b0, B1 = b2 - a2 * b0;
    const m00 = 1 + a1, m01 = -1, m10 = a2, m11 = 1;
    const det = m00 * m11 - m01 * m10;
    return [(B0 * m11 - m01 * B1) / det, (m00 * B1 - m10 * B0) / det];
  }

  function sosfiltZi(sos) {
    const zi = [];
    let scale = 1.0;
    for (const s of sos) {
      const z = lfilterZi2(s[0], s[1], s[2], s[4], s[5]);
      zi.push([z[0] * scale, z[1] * scale]);
      scale *= (s[0] + s[1] + s[2]) / (s[3] + s[4] + s[5]);
    }
    return zi;
  }

  /** Direct-form II transposed SOS filtering of a 1-D array (scipy sosfilt), zi per section. */
  function sosfilt1(sos, x, zi) {
    const n = x.length, y = new Float64Array(n);
    const ns = sos.length;
    const z = zi ? zi.map((v) => [v[0], v[1]]) : sos.map(() => [0, 0]);
    for (let i = 0; i < n; i++) {
      let v = x[i];
      for (let s = 0; s < ns; s++) {
        const c = sos[s], zz = z[s];
        const out = c[0] * v + zz[0];
        zz[0] = c[1] * v - c[4] * out + zz[1];
        zz[1] = c[2] * v - c[5] * out;
        v = out;
      }
      y[i] = v;
    }
    return { y, z };
  }

  function sosfiltfilt1(sos, x, ziBase, padlen) {
    const n = x.length;
    if (n <= padlen) padlen = n - 1;
    const ext = new Float64Array(n + 2 * padlen);
    for (let i = 0; i < padlen; i++) ext[i] = 2 * x[0] - x[padlen - i];
    for (let i = 0; i < n; i++) ext[padlen + i] = x[i];
    for (let i = 0; i < padlen; i++) ext[padlen + n + i] = 2 * x[n - 1] - x[n - 2 - i];
    const zf = ziBase.map((z) => [z[0] * ext[0], z[1] * ext[0]]);
    let y = sosfilt1(sos, ext, zf).y;
    y.reverse();
    const zb = ziBase.map((z) => [z[0] * y[0], z[1] * y[0]]);
    y = sosfilt1(sos, y, zb).y;
    y.reverse();
    return y.subarray(padlen, padlen + n);
  }

  const sosCache = new Map();
  function bandSOS(cfg, fs, lo) {
    const band = PROFILES[cfg.profile].band;
    const l = lo === undefined ? band[0] : lo;
    const a = l * 0.8, b = Math.min(band[1] * 1.15, 0.45 * fs);
    const key = a.toFixed(12) + '|' + b.toFixed(12) + '|' + fs;
    if (!sosCache.has(key)) {
      const sos = butterBandpassSOS(a, b, fs);
      sosCache.set(key, { sos, zi: sosfiltZi(sos), padlen: 21 });
    }
    return sosCache.get(key);
  }

  // ------------------------------------------------------------------ per-packet sanitisation
  function unwrapInPlace(p) {
    let corr = 0;
    let prev = p[0];
    for (let i = 1; i < p.length; i++) {
      const cur = p[i];
      const dd = cur - prev;
      let ddmod = ((dd + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
      if (ddmod === -Math.PI && dd > 0) ddmod = Math.PI;
      let pc = ddmod - dd;
      if (Math.abs(dd) < Math.PI) pc = 0;
      corr += pc;
      prev = cur;
      p[i] = cur + corr;
    }
  }

  function sanitizePackets(link) {
    const slots = validSlots(link.fwi);
    const C_ = slots.length;
    const kc = new Float64Array(C_);
    let km = 0;
    for (let j = 0; j < C_; j++) km += SLOT_TO_SC[slots[j]];
    km /= C_;
    let kss = 0;
    for (let j = 0; j < C_; j++) { kc[j] = SLOT_TO_SC[slots[j]] - km; kss += kc[j] * kc[j]; }
    const n = link.t.length;
    const shape = new Array(n), phase = new Array(n), rms = new Float64Array(n);
    const A = new Float64Array(C_), P = new Float64Array(C_);
    for (let i = 0; i < n; i++) {
      const h = link.H[i];
      let ss = 0;
      for (let j = 0; j < C_; j++) {
        const s = slots[j];
        const re = h.re[s], im = h.im[s];
        A[j] = Math.hypot(re, im);
        P[j] = Math.atan2(im, re);
        ss += A[j] * A[j];
      }
      const r = Math.sqrt(ss / C_) + 1e-9;
      rms[i] = fround(r);
      unwrapInPlace(P);
      let slope = 0, icpt = 0;
      for (let j = 0; j < C_; j++) { slope += P[j] * kc[j]; icpt += P[j]; }
      slope /= kss; icpt /= C_;
      const sh = new Float64Array(C_), ph = new Float64Array(C_);
      for (let j = 0; j < C_; j++) {
        sh[j] = fround(A[j] / r);
        ph[j] = fround(P[j] - (slope * kc[j] + icpt));
      }
      shape[i] = sh; phase[i] = ph;
    }
    return { shape, phase, rms, nch: C_ };
  }

  // ------------------------------------------------------------------ features on a uniform grid
  // Middle element of a after sorting it with (x, y) => x - y, which is a stable sort, so equal values keep their order.
  // A stable insertion sort into a reused buffer gives the same element; a window holding NaN takes the original path,
  // because the comparator then is not consistent. (v1.3.2+: this alone was about 70% of the live pipeline's time.)
  function sortedMid(a, tmp, n, half) {
    for (let i = 0; i < n; i++) {
      const x = a[i];
      if (x !== x) return Array.from(a).sort((p, q) => p - q)[half];
      let j = i;
      while (j > 0 && tmp[j - 1] - x > 0) { tmp[j] = tmp[j - 1]; j--; }
      tmp[j] = x;
    }
    return tmp[half];
  }
  function hampelTime(X, T, Cn, win, nSigma) {
    const half = win >> 1;
    const out = new Float64Array(T * Cn);
    const buf = new Float64Array(win), dev = new Float64Array(win), tmp = new Float64Array(win);
    for (let c = 0; c < Cn; c++) {
      for (let i = 0; i < T; i++) {
        for (let k = 0; k < win; k++) {
          let idx = i - half + k;
          if (idx < 0) idx = 0; else if (idx >= T) idx = T - 1;
          buf[k] = X[idx * Cn + c];
        }
        const med = sortedMid(buf, tmp, win, half);
        for (let k = 0; k < win; k++) dev[k] = Math.abs(buf[k] - med);
        const md = sortedMid(dev, tmp, win, half);
        const mad = 1.4826 * md + 1e-12;
        const v = X[i * Cn + c];
        out[i * Cn + c] = Math.abs(v - med) > nSigma * mad ? med : v;
      }
    }
    return out;
  }

  function linkFeatures(link, fs, tEnd, opts) {
    opts = opts || {};
    const san = sanitizePackets(link);
    const Cs = san.nch, Cn = 2 * Cs;
    const t = link.t, n = t.length;
    const t0 = t[0];
    tEnd = tEnd === undefined ? t[n - 1] : tEnd;
    const T = Math.max(0, Math.ceil((tEnd - t0) * fs - 1e-9));
    const tu = new Float64Array(T);
    for (let i = 0; i < T; i++) tu[i] = t0 + i / fs;
    // resample each channel by linear interpolation
    const X = new Float64Array(T * Cn);
    let lo = 0;
    const gap = new Uint8Array(T);
    for (let i = 0; i < T; i++) {
      const x = tu[i];
      while (lo < n - 2 && t[lo + 1] <= x) lo++;
      let a = lo, b = lo + 1;
      let w;
      if (x <= t[0]) { a = 0; b = 0; w = 0; }
      else if (x >= t[n - 1]) { a = n - 1; b = n - 1; w = 0; }
      else { const dx = t[b] - t[a]; w = dx > 0 ? (x - t[a]) / dx : 1; }
      const sa = san.shape[a], sb = san.shape[b], pa = san.phase[a], pb = san.phase[b];
      const row = i * Cn;
      for (let c = 0; c < Cs; c++) {
        X[row + c] = w === 0 ? sa[c] : sa[c] + (sb[c] - sa[c]) * w;
        X[row + Cs + c] = w === 0 ? pa[c] : pa[c] + (pb[c] - pa[c]) * w;
      }
      // gap: nearest real sample farther than 0.5 s
      let idx = searchsortedLeft(t, x);
      idx = Math.min(Math.max(idx, 1), n - 1);
      const near = Math.min(Math.abs(x - t[idx - 1]), Math.abs(t[idx] - x));
      gap[i] = near > 0.5 ? 1 : 0;
    }
    const win = Math.max(5, Math.round(0.7 * fs)) | 1;
    const Xh = hampelTime(X, T, Cn, win, 3.0);
    const rmsDb = new Float64Array(T), rssi = new Float64Array(T);
    const lr = new Float64Array(n);
    for (let i = 0; i < n; i++) lr[i] = fround(20 * Math.log10(san.rms[i]));
    for (let i = 0; i < T; i++) { rmsDb[i] = interp1(tu[i], t, lr); rssi[i] = interp1(tu[i], t, link.rssi); }
    // movement index
    const k = Math.max(2, Math.round(fs));
    const means = new Float64Array(T * Cs);
    const csum = new Float64Array(Cs);
    const hist = [];
    for (let i = 0; i < T; i++) {
      // trailing mean over last k samples of shape channels
      for (let c = 0; c < Cs; c++) csum[c] += Xh[i * Cn + c];
      hist.push(i);
      if (hist.length > k) { const j = hist.shift(); for (let c = 0; c < Cs; c++) csum[c] -= Xh[j * Cn + c]; }
      const cnt = hist.length;
      for (let c = 0; c < Cs; c++) means[i * Cs + c] = csum[c] / cnt;
    }
    const dec = new Float64Array(T);
    for (let i = 0; i < T; i++) {
      const j = i < k ? i : i - k;
      let m0 = 0, m1 = 0;
      for (let c = 0; c < Cs; c++) { m0 += means[i * Cs + c]; m1 += means[j * Cs + c]; }
      m0 /= Cs; m1 /= Cs;
      let sxy = 0, sxx = 0, syy = 0;
      for (let c = 0; c < Cs; c++) {
        const a0 = means[i * Cs + c] - m0, a1 = means[j * Cs + c] - m1;
        sxy += a0 * a1; sxx += a0 * a0; syy += a1 * a1;
      }
      dec[i] = 1 - sxy / Math.sqrt(sxx * syy + 1e-12);
    }
    const r2 = Math.round(2 * fs);
    const rsd = new Float64Array(T);
    let s1 = 0, s2 = 0;
    const q = [];
    for (let i = 0; i < T; i++) {
      s1 += rssi[i]; s2 += rssi[i] * rssi[i]; q.push(rssi[i]);
      if (q.length > r2) { const v = q.shift(); s1 -= v; s2 -= v * v; }
      const cnt = q.length, mu = s1 / cnt;
      rsd[i] = Math.sqrt(Math.max(s2 / cnt - mu * mu, 0));
    }
    const medR = opts.medRssiSd !== undefined ? opts.medRssiSd : median(rsd);
    const medD = opts.medDec !== undefined ? opts.medDec : median(dec);
    const activity = new Float64Array(T);
    for (let i = 0; i < T; i++) activity[i] = Math.max((rsd[i] / Math.max(medR, 0.25)) / 3.5, (dec[i] / (medD + 1e-9)) / 25.0);
    return { label: link.label, mac: link.mac, fs, t: tu, X: Xh, T, Cn, gap, activity, rmsDb, rssi, medRssiSd: medR, medDec: medD, rsd, dec };
  }

  // ------------------------------------------------------------------ symmetric eigen (cyclic Jacobi)
  function jacobiEig(Ain, n) {
    const A = Float64Array.from(Ain);
    const V = new Float64Array(n * n);
    for (let i = 0; i < n; i++) V[i * n + i] = 1;
    for (let sweep = 0; sweep < 60; sweep++) {
      let off = 0, diag = 0;
      for (let p = 0; p < n; p++) { diag += A[p * n + p] * A[p * n + p]; for (let q = p + 1; q < n; q++) off += A[p * n + q] * A[p * n + q]; }
      if (off <= 1e-22 * diag || off === 0) break;
      for (let p = 0; p < n - 1; p++) {
        for (let q = p + 1; q < n; q++) {
          const apq = A[p * n + q];
          if (Math.abs(apq) < 1e-300) continue;
          const app = A[p * n + p], aqq = A[q * n + q];
          const theta = (aqq - app) / (2 * apq);
          const tt = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
          const c = 1 / Math.sqrt(tt * tt + 1), s = tt * c;
          for (let k = 0; k < n; k++) {
            const akp = A[k * n + p], akq = A[k * n + q];
            A[k * n + p] = c * akp - s * akq;
            A[k * n + q] = s * akp + c * akq;
          }
          for (let k = 0; k < n; k++) {
            const apk = A[p * n + k], aqk = A[q * n + k];
            A[p * n + k] = c * apk - s * aqk;
            A[q * n + k] = s * apk + c * aqk;
          }
          for (let k = 0; k < n; k++) {
            const vkp = V[k * n + p], vkq = V[k * n + q];
            V[k * n + p] = c * vkp - s * vkq;
            V[k * n + q] = s * vkp + c * vkq;
          }
        }
      }
    }
    const vals = new Float64Array(n);
    for (let i = 0; i < n; i++) vals[i] = A[i * n + i];
    const idx = Array.from({ length: n }, (_, i) => i).sort((a, b) => vals[b] - vals[a]);
    return { vals: idx.map((i) => vals[i]), vecs: idx.map((i) => { const v = new Float64Array(n); for (let k = 0; k < n; k++) v[k] = V[k * n + i]; return v; }) };
  }


  // ------------------------------------------------------------------ symmetric eigen (JAMA tred2 + tql2, public domain)
  function symEig(Ain, n) {
    const V = new Array(n);
    for (let i = 0; i < n; i++) { V[i] = new Float64Array(n); for (let j = 0; j < n; j++) V[i][j] = Ain[i * n + j]; }
    const d = new Float64Array(n), e = new Float64Array(n);
    // tred2
    for (let j = 0; j < n; j++) d[j] = V[n - 1][j];
    for (let i = n - 1; i > 0; i--) {
      let scale = 0, h = 0;
      for (let k = 0; k < i; k++) scale += Math.abs(d[k]);
      if (scale === 0) {
        e[i] = d[i - 1];
        for (let j = 0; j < i; j++) { d[j] = V[i - 1][j]; V[i][j] = 0; V[j][i] = 0; }
      } else {
        for (let k = 0; k < i; k++) { d[k] /= scale; h += d[k] * d[k]; }
        let f = d[i - 1];
        let g = Math.sqrt(h);
        if (f > 0) g = -g;
        e[i] = scale * g; h = h - f * g; d[i - 1] = f - g;
        for (let j = 0; j < i; j++) e[j] = 0;
        for (let j = 0; j < i; j++) {
          f = d[j]; V[j][i] = f; g = e[j] + V[j][j] * f;
          for (let k = j + 1; k <= i - 1; k++) { g += V[k][j] * d[k]; e[k] += V[k][j] * f; }
          e[j] = g;
        }
        f = 0;
        for (let j = 0; j < i; j++) { e[j] /= h; f += e[j] * d[j]; }
        const hh = f / (h + h);
        for (let j = 0; j < i; j++) e[j] -= hh * d[j];
        for (let j = 0; j < i; j++) {
          f = d[j]; g = e[j];
          for (let k = j; k <= i - 1; k++) V[k][j] -= (f * e[k] + g * d[k]);
          d[j] = V[i - 1][j]; V[i][j] = 0;
        }
      }
      d[i] = h;
    }
    for (let i = 0; i < n - 1; i++) {
      V[n - 1][i] = V[i][i]; V[i][i] = 1;
      const h = d[i + 1];
      if (h !== 0) {
        for (let k = 0; k <= i; k++) d[k] = V[k][i + 1] / h;
        for (let j = 0; j <= i; j++) {
          let g = 0;
          for (let k = 0; k <= i; k++) g += V[k][i + 1] * V[k][j];
          for (let k = 0; k <= i; k++) V[k][j] -= g * d[k];
        }
      }
      for (let k = 0; k <= i; k++) V[k][i + 1] = 0;
    }
    for (let j = 0; j < n; j++) { d[j] = V[n - 1][j]; V[n - 1][j] = 0; }
    V[n - 1][n - 1] = 1; e[0] = 0;
    // tql2
    for (let i = 1; i < n; i++) e[i - 1] = e[i];
    e[n - 1] = 0;
    let f = 0, tst1 = 0;
    const eps = Math.pow(2, -52);
    for (let l = 0; l < n; l++) {
      tst1 = Math.max(tst1, Math.abs(d[l]) + Math.abs(e[l]));
      let m = l;
      while (m < n) { if (Math.abs(e[m]) <= eps * tst1) break; m++; }
      if (m > l) {
        let iter = 0;
        do {
          iter++;
          let g = d[l];
          let p = (d[l + 1] - g) / (2 * e[l]);
          let r = Math.hypot(p, 1);
          if (p < 0) r = -r;
          d[l] = e[l] / (p + r);
          d[l + 1] = e[l] * (p + r);
          const dl1 = d[l + 1];
          let h = g - d[l];
          for (let i = l + 2; i < n; i++) d[i] -= h;
          f += h;
          p = d[m];
          let c = 1, c2 = c, c3 = c, el1 = e[l + 1], s = 0, s2 = 0;
          for (let i = m - 1; i >= l; i--) {
            c3 = c2; c2 = c; s2 = s;
            g = c * e[i]; h = c * p; r = Math.hypot(p, e[i]);
            e[i + 1] = s * r; s = e[i] / r; c = p / r; p = c * d[i] - s * g;
            d[i + 1] = h + s * (c * g + s * d[i]);
            for (let k = 0; k < n; k++) { h = V[k][i + 1]; V[k][i + 1] = s * V[k][i] + c * h; V[k][i] = c * V[k][i] - s * h; }
          }
          p = -s * s2 * c3 * el1 * e[l] / dl1;
          e[l] = s * p; d[l] = c * p;
        } while (Math.abs(e[l]) > eps * tst1 && iter < 100);
      }
      d[l] = d[l] + f; e[l] = 0;
    }
    const idx = Array.from({ length: n }, (_, i) => i).sort((a, b) => d[b] - d[a]);
    return { vals: idx.map((i) => d[i]), vecs: idx.map((i) => { const v = new Float64Array(n); for (let k = 0; k < n; k++) v[k] = V[k][i]; return v; }) };
  }

  // ------------------------------------------------------------------ radix-2 FFT (power-of-two length)
  const fftCache = new Map();
  function fftPlan(N) {
    if (fftCache.has(N)) return fftCache.get(N);
    const rev = new Uint32Array(N);
    const bits = Math.round(Math.log2(N));
    for (let i = 0; i < N; i++) { let r = 0, x = i; for (let b = 0; b < bits; b++) { r = (r << 1) | (x & 1); x >>= 1; } rev[i] = r; }
    const cos = new Float64Array(N / 2), sin = new Float64Array(N / 2);
    for (let i = 0; i < N / 2; i++) { cos[i] = Math.cos(2 * Math.PI * i / N); sin[i] = -Math.sin(2 * Math.PI * i / N); }
    const plan = { N, rev, cos, sin };
    fftCache.set(N, plan);
    return plan;
  }
  function fftReal(x, N) {
    const P = fftPlan(N);
    const re = new Float64Array(N), im = new Float64Array(N);
    for (let i = 0; i < x.length && i < N; i++) re[P.rev[i]] = x[i];
    for (let size = 2; size <= N; size <<= 1) {
      const half = size >> 1, step = N / size;
      for (let i = 0; i < N; i += size) {
        for (let j = 0, k = 0; j < half; j++, k += step) {
          const tr = re[i + j + half] * P.cos[k] - im[i + j + half] * P.sin[k];
          const ti = re[i + j + half] * P.sin[k] + im[i + j + half] * P.cos[k];
          re[i + j + half] = re[i + j] - tr; im[i + j + half] = im[i + j] - ti;
          re[i + j] += tr; im[i + j] += ti;
        }
      }
    }
    return { re, im };
  }

  function parabolicPeak(y, i) {
    if (i > 0 && i < y.length - 1) {
      const a = y[i - 1], b = y[i], c = y[i + 1], den = a - 2 * b + c;
      if (den !== 0) return i + 0.5 * (a - c) / den;
    }
    return i;
  }

  function findPeaks(x) {
    // scipy.signal.find_peaks without conditions (handles flat peaks: middle index)
    const peaks = [];
    let i = 1;
    const imax = x.length - 1;
    while (i < imax) {
      if (x[i - 1] < x[i]) {
        let ahead = i + 1;
        while (ahead < imax && x[ahead] === x[i]) ahead++;
        if (x[ahead] < x[i]) {
          const left = i, right = ahead - 1;
          peaks.push((left + right) >> 1);
          i = ahead;
        }
      }
      i++;
    }
    return peaks;
  }

  // ------------------------------------------------------------------ window estimate
  function estimateWindow(F, s0, e, cfg) {
    const fs = F.fs, Cn = F.Cn, n = e - s0;
    const band = PROFILES[cfg.profile].band;
    let lo = Math.max(band[0], 2.0 / (n / fs));
    const hi = band[1];
    const filt = bandSOS(cfg, fs, lo);
    // demean + zero-phase band-pass, per channel
    const Xf = new Float64Array(n * Cn);
    const col = new Float64Array(n);
    const sd = new Float64Array(Cn);
    for (let c = 0; c < Cn; c++) {
      let m = 0;
      for (let i = 0; i < n; i++) { col[i] = F.X[(s0 + i) * Cn + c]; m += col[i]; }
      m /= n;
      for (let i = 0; i < n; i++) col[i] -= m;
      const y = sosfiltfilt1(filt.sos, col, filt.zi, filt.padlen);
      let mm = 0;
      for (let i = 0; i < n; i++) { Xf[i * Cn + c] = y[i]; mm += y[i]; }
      mm /= n;
      let ss = 0;
      for (let i = 0; i < n; i++) { const d = y[i] - mm; ss += d * d; }
      sd[c] = Math.sqrt(ss / n);
    }
    const keep = [];
    for (let c = 0; c < Cn; c++) if (sd[c] > 1e-9) keep.push(c);
    const K = keep.length;
    const Z = new Float64Array(n * K);
    for (let i = 0; i < n; i++) for (let j = 0; j < K; j++) Z[i * K + j] = Xf[i * Cn + keep[j]] / sd[keep[j]];
    // covariance Z^T Z
    const Cv = new Float64Array(K * K);
    for (let a = 0; a < K; a++) {
      for (let b = a; b < K; b++) {
        let s = 0;
        for (let i = 0; i < n; i++) s += Z[i * K + a] * Z[i * K + b];
        Cv[a * K + b] = s; Cv[b * K + a] = s;
      }
    }
    const eig = symEig(Cv, K);
    const totalVar = eig.vals.reduce((s, v) => s + Math.max(v, 0), 0);
    const nfft = 8192, df = fs / nfft;
    const kLo = Math.ceil(lo / df - 1e-9), kHi = Math.floor(hi / df + 1e-9);
    const win = hanning(n);
    let best = null;
    const npc = Math.min(cfg.n_pcs, K);
    for (let c = 0; c < npc; c++) {
      const v = eig.vecs[c];
      const pc = new Float64Array(n);
      for (let i = 0; i < n; i++) { let s = 0; for (let j = 0; j < K; j++) s += Z[i * K + j] * v[j]; pc[i] = s; }
      const xw = new Float64Array(n);
      for (let i = 0; i < n; i++) xw[i] = pc[i] * win[i];
      const nb = kHi - kLo + 1;
      const Pb = new Float64Array(nb);
      const spec = fftReal(xw, nfft);
      for (let k = 0; k < nb; k++) { const kk = kLo + k; Pb[k] = spec.re[kk] * spec.re[kk] + spec.im[kk] * spec.im[kk]; }
      let ib = 0;
      for (let k = 1; k < nb; k++) if (Pb[k] > Pb[ib]) ib = k;
      const fpk = kLo * df + parabolicPeak(Pb, ib) * df;
      let near = 0, tot = 0;
      for (let k = 0; k < nb; k++) { tot += Pb[k]; if (Math.abs((kLo + k) * df - fpk) <= cfg.peak_halfwidth_hz) near += Pb[k]; }
      const prom = near / (tot + 1e-12);
      if (!best || prom > best.prominence) best = { pc: c, f_spec: fpk, prominence: prom, series: pc, weights: v, explained: Math.max(eig.vals[c], 0) / (totalVar || 1) };
    }
    // autocorrelation of the chosen component
    const pc = best.series;
    const m = mean(pc);
    const x = new Float64Array(n);
    for (let i = 0; i < n; i++) x[i] = pc[i] - m;
    const lagLo = Math.floor(fs / hi);
    let lagHi = Math.ceil(fs / lo);
    lagHi = Math.min(lagHi, n - 2);
    let ac0 = 0;
    for (let i = 0; i < n; i++) ac0 += x[i] * x[i];
    const seg = new Float64Array(Math.max(0, lagHi - lagLo + 1));
    for (let L = lagLo; L <= lagHi; L++) { let s = 0; for (let i = 0; i + L < n; i++) s += x[i] * x[i + L]; seg[L - lagLo] = s / (ac0 + 1e-12); }
    const pk = findPeaks(seg);
    let fAcf = NaN, acfH = 0;
    if (pk.length) {
      let j = pk[0];
      for (const p of pk) if (seg[p] > seg[j]) j = p;
      const lag = lagLo + parabolicPeak(seg, j);
      fAcf = fs / lag; acfH = seg[j];
    }
    const bpmS = best.f_spec * 60, bpmA = fAcf * 60;
    const agree = Number.isFinite(bpmA) && Math.abs(bpmS - bpmA) <= cfg.agree_bpm;
    return { bpm_spec: bpmS, bpm_acf: bpmA, prominence: best.prominence, acf: acfH, agree, pc: best.pc,
      waveform: best.series, weights: best.weights, keep, sd, Xf, explained: best.explained };
  }

  function narrowbandAmp(p, fs, f0, spread, boxcar) {
    spread = spread === undefined ? 0.05 : spread;
    const n = p.length;
    if (n < 4 || !Number.isFinite(f0)) return NaN;
    const w = boxcar ? new Float64Array(n).fill(1) : hanning(n);
    const m = mean(p);
    let wsum = 0;
    for (let i = 0; i < n; i++) wsum += w[i];
    let best = 0;
    for (let q = 0; q < 5; q++) {
      const f = f0 + (-spread + q * (2 * spread / 4));
      if (f <= 0) continue;
      let re = 0, im = 0;
      for (let i = 0; i < n; i++) { const x = (p[i] - m) * w[i]; const ang = -2 * Math.PI * f * (i / fs); re += x * Math.cos(ang); im += x * Math.sin(ang); }
      best = Math.max(best, Math.hypot(re, im));
    }
    return 2.0 * best / wsum;
  }

  /** v1.3.2 recency check: newest block's RMS over the strongest earlier block (blocks laid back from
   * the window's end, each at least recentS long and one breath at bpm). NaN when fewer than two fit. */
  function recentRatio(pc, fs, bpm, recentS) {
    if (!Number.isFinite(bpm) || bpm <= 0) return NaN;
    const n = roundHalfEven(Math.max(recentS, 60.0 / bpm) * fs);
    const m = Math.floor(pc.length / n);
    if (n < 2 || m < 2) return NaN;
    const off = pc.length - m * n;
    let last = 0, best = 0;
    for (let b = 0; b < m; b++) {
      let ss = 0;
      for (let i = off + b * n; i < off + (b + 1) * n; i++) ss += pc[i] * pc[i];
      const r = Math.sqrt(ss / n);
      if (b === m - 1) last = r; else if (r > best) best = r;
    }
    return last / (best + 1e-12);
  }

  class SwingCounter {
    constructor(h, t0, x0) { this.h = h; this.last_t = t0; this.reset(x0); }
    reset(x0) { this.mode = 0; this.hi = x0; this.lo = x0; }
    update(t, x) {
      if (this.mode === 0) {
        this.hi = Math.max(this.hi, x); this.lo = Math.min(this.lo, x);
        if (this.hi - x > this.h) { this.last_t = t; this.mode = -1; this.lo = x; }
        else if (x - this.lo > this.h) { this.last_t = t; this.mode = 1; this.hi = x; }
      } else if (this.mode === 1) {
        if (x > this.hi) this.hi = x;
        else if (this.hi - x > this.h) { this.last_t = t; this.mode = -1; this.lo = x; }
      } else {
        if (x < this.lo) this.lo = x;
        else if (x - this.lo > this.h) { this.last_t = t; this.mode = 1; this.hi = x; }
      }
    }
  }

  // ------------------------------------------------------------------ tracking (window loop + causal pause)
  function trackLink(F, cfg) {
    const fs = F.fs, Cn = F.Cn, T = F.T;
    const nw = Math.round(cfg.win_s * fs), nh = Math.round(cfg.hop_s * fs);
    const nTail = Math.round(6 * fs);
    const thr = 1.0;
    const k = Math.max(1, Math.round(fs));
    // np.convolve(activity, ones(k)/k, 'same')
    const act = new Float64Array(T);
    const off = (k - 1) >> 1;
    for (let i = 0; i < T; i++) {
      let s = 0;
      for (let j = 0; j < k; j++) { const idx = i + off - j; if (idx >= 0 && idx < T) s += F.activity[idx]; }
      act[i] = s / k;
    }
    // causal band-pass of all channels for the pause detector
    const fc = bandSOS(cfg, fs);
    const nRef = Math.min(Math.round(5 * fs), T);
    const xref = new Float64Array(Cn);
    for (let c = 0; c < Cn; c++) { let s = 0; for (let i = 0; i < nRef; i++) s += F.X[i * Cn + c]; xref[c] = s / nRef; }
    const Xc = new Float64Array(T * Cn);
    const colb = new Float64Array(T);
    for (let c = 0; c < Cn; c++) {
      for (let i = 0; i < T; i++) colb[i] = F.X[i * Cn + c] - xref[c];
      const y = sosfilt1(fc.sos, colb, null).y;
      for (let i = 0; i < T; i++) Xc[i * Cn + c] = y[i];
    }
    const pauseMin = cfg.profile === 'adult' ? 10.0 : 20.0;
    const out = { t: [], bpm: [], bpm_raw: [], prom: [], acf: [], rel: [], mot: [], q: [], pause: [], quiet: [], snr: [], period: [], wave: [], recent: [], recentLow: [], gated: [] };
    let base = null, swing = null, prevE = 0;
    const nMinClean = Math.round(cfg.min_clean_s * fs);
    const proj = (lo, hi, b) => {
      const r = new Float64Array(hi - lo);
      for (let i = lo; i < hi; i++) { let s = 0; for (let j = 0; j < b.keep.length; j++) { const c = b.keep[j]; s += (Xc[i * Cn + c] / b.sd[c]) * b.w[j]; } r[i - lo] = s; }
      return r;
    };
    let lastWave = null, lastShown = null;
    for (let e = nw; e <= T; e += nh) {
      let s0 = e - nw;
      let movingNow = false;
      for (let i = e - nTail; i < e; i++) if (act[i] > thr) { movingNow = true; break; }
      let lastHot = -1;
      for (let i = s0; i < e; i++) if (act[i] > thr) lastHot = i - s0;
      let contaminated = false;
      if (lastHot >= 0) {
        const sClean = s0 + lastHot + Math.round(1 * fs) + 1;
        if (e - sClean >= nMinClean) s0 = sClean; else contaminated = true;
      }
      let movedSince = false;
      for (let i = prevE; i < e; i++) if (act[i] > thr) { movedSince = true; break; }
      if (movedSince) { base = null; swing = null; }
      let pauseS = NaN, quiet = NaN;
      if (base && swing) {
        const p = proj(prevE, e, base);
        for (let i = 0; i < p.length; i++) swing.update(F.t[prevE + i], p[i]);
        pauseS = F.t[e - 1] - swing.last_t;
        // v1.3.1: breathing-band amplitude over the last need + 10 s with equal weights
        const need = Math.max(pauseMin, base.period);
        const nQ = roundHalfEven((need + 10.0) * fs);
        if (e - nQ >= base.start) {
          const sq = proj(e - nQ, e, base);
          quiet = narrowbandAmp(sq, fs, base.f, 0.05, true) / (base.nb + 1e-12);
        }
      }
      prevE = e;
      let gapSum = 0;
      for (let i = s0; i < e; i++) gapSum += F.gap[i];
      const gapFrac = gapSum / (e - s0);
      const r = estimateWindow(F, s0, e, cfg);
      const q = Math.min(1, Math.max(0, 0.5 * (r.prominence / 0.6) + 0.5 * (r.acf / 0.7)));
      const periodic = r.agree && r.prominence >= cfg.min_prominence && r.acf >= cfg.min_acf && !contaminated && gapFrac <= cfg.max_gap_frac;
      // v1.3.2 recency check: a rate is shown only if breathing is still present in the newest block
      const rr = recentRatio(r.waveform, fs, r.bpm_spec, cfg.recent_s);
      const recentLow = Number.isFinite(rr) && rr < cfg.recent_min_ratio;
      const reliable = periodic && !recentLow;
      if (periodic) { // the pause baseline still learns from every window with clear breathing
        const bb = { keep: r.keep, sd: r.sd, w: r.weights };
        const pc = proj(s0, e, bb);
        const ss = Math.round(3 * fs);
        const winRms = stdPop(pc, ss, pc.length);
        const tailRms = stdPop(pc, Math.max(0, pc.length - Math.round(pauseMin * fs)), pc.length);
        if (!base || tailRms >= 0.6 * winRms) {
          const amp = Math.SQRT2 * winRms;
          const fresh = !base;
          const since = fresh ? e : base.since;
          const start = fresh ? s0 : base.start;
          const fB = Math.max(r.bpm_spec, 1.0) / 60.0;
          const nR = roundHalfEven((Math.max(pauseMin, 1.0 / fB) + 10.0) * fs);
          const ref = pc.subarray(Math.max(0, pc.length - nR));
          const nbSig = narrowbandAmp(ref, fs, fB, 0.05, true);
          const band = PROFILES[cfg.profile].band;
          const offs = [fB - 0.30, fB - 0.20, fB + 0.20, fB + 0.30].filter((f) => f >= band[0] && f <= band[1]);
          const nbNoise = offs.length ? median(offs.map((f) => narrowbandAmp(ref, fs, f, 0.0, true))) : NaN;
          base = { keep: r.keep, sd: r.sd, w: r.weights, amp, rms: winRms, since, start, period: 1.0 / fB, f: fB, nb: nbSig,
            snr: Number.isFinite(nbNoise) ? nbSig / (nbNoise + 1e-12) : NaN };
          if (fresh || !swing) swing = new SwingCounter(0.8 * amp, F.t[e - 1], pc[pc.length - 1]);
          else { swing.h = 0.8 * amp; swing.reset(pc[pc.length - 1]); }
        }
      }
      out.t.push(F.t[e - 1]); out.bpm_raw.push(r.bpm_spec); out.bpm.push(reliable ? r.bpm_spec : NaN);
      out.prom.push(r.prominence); out.acf.push(r.acf); out.rel.push(reliable); out.mot.push(movingNow);
      out.q.push(contaminated ? 0 : q); out.pause.push(pauseS); out.quiet.push(quiet);
      out.snr.push(base ? base.snr : NaN); out.period.push(base ? base.period : NaN);
      out.recent.push(rr); out.recentLow.push(recentLow); out.gated.push(periodic && recentLow);
      // display waveform: last hop of the chosen component, sign-aligned with the previous hop
      const w = r.waveform;
      const sdw = stdPop(w) + 1e-12;
      let flip = false;
      if (lastWave) {
        // align sign using the overlap with the previous window's tail
        let dot = 0;
        const L = Math.min(lastWave.length, w.length - nh);
        for (let i = 0; i < L; i++) dot += lastWave[lastWave.length - L + i] * (w[w.length - nh - L + i] / sdw);
        flip = dot < 0;
      }
      const wn = (flip ? -1 : 1) / sdw;
      const seg = Array.from(w.subarray(w.length - nh), (v) => v * wn);
      // display only: blend out the step between this window and the previous hop on screen
      if (lastShown !== null && w.length > nh) {
        const d = lastShown - w[w.length - nh - 1] * wn;
        for (let j = 0; j < nh; j++) seg[j] += d * (1 - (j + 1) / nh);
      }
      lastShown = seg[nh - 1];
      out.wave.push(seg);
      // keep the displayed (sign-corrected) window so the next hop aligns to what is on screen
      lastWave = Array.from(w, (v) => v * wn);
    }
    const trk = { label: F.label, mac: F.mac, t: out.t, bpm: out.bpm, bpm_raw: out.bpm_raw, prominence: out.prom, acf: out.acf,
      reliable: out.rel, motion: out.mot, quality: out.q, pause_s: out.pause, quiet: out.quiet, pause_snr: out.snr,
      base_period: out.period, wave: out.wave, profile: cfg.profile, recent_ratio: out.recent, recent_low: out.recentLow, recent_gated: out.gated };
    const sf = screeningFlags(trk, cfg);
    trk.status = sf.status; trk.reason = sf.reason; trk.reasonKey = sf.key; trk.pause_est = sf.pause_est;
    return trk;
  }

  // ------------------------------------------------------------------ screening flags
  const STATUS_ORDER = { urgent: 3, watch: 2, typical: 1, no_reading: 0, moving: 0 };

  function classifyRate(bpm, profile) {
    if (!Number.isFinite(bpm)) return ['no_reading', 'No reliable reading', 'noread'];
    if (profile === 'adult') {
      if (bpm <= 8.5) return ['urgent', 'Very slow breathing', 'veryslow'];
      if (bpm < 11.5) return ['watch', 'Slow breathing', 'slow'];
      if (bpm <= 20.5) return ['typical', 'Typical breathing rate', 'typical'];
      if (bpm < 24.5) return ['watch', 'Fast breathing', 'fast'];
      return ['urgent', 'Very fast breathing', 'veryfast'];
    }
    const cut = { newborn_lt2m: 60, infant_2_12m: 50, child_1_5y: 40 }[profile];
    if (bpm >= cut) return [profile === 'newborn_lt2m' ? 'urgent' : 'watch', 'Fast breathing for age (>= ' + cut + '/min)', 'fastage'];
    if (bpm < { newborn_lt2m: 25, infant_2_12m: 20, child_1_5y: 15 }[profile]) return ['watch', 'Slow breathing for age', 'slowage'];
    return ['typical', 'Typical breathing rate for age', 'typicalage'];
  }

  function screeningFlags(trk, cfg, opt) {
    opt = opt || {};
    const persistHops = opt.persist_hops || 2;
    const pauseMinS = opt.pause_min_s || (cfg.profile === 'adult' ? 10.0 : 20.0);
    const minPauseSnr = opt.min_pause_snr || 3.0, noReadAfter = opt.no_reading_after_s || 20.0;
    const quietPersist = opt.quiet_persist_hops || 2, swingResumeSnr = opt.swing_resume_snr || 6.0;
    const n = trk.t.length;
    const status = [], reason = [], key = [], pauseEst = new Array(n).fill(NaN);
    let current = 'no_reading', curReason = 'Warming up (first 30 s)', curKey = 'warmup';
    let pending = null, pendingN = 0, lastGood = -1e9, smooth = [], latched = false, resumedUntil = -1e9, lastResume = -1e9;
    let quietRun = 0, latchT0 = 0, latchEst0 = 0, lastRateT = -1e9;
    const pauseLabel = 'Possible breathing pause (>= ' + Math.trunc(pauseMinS) + ' s)';
    const resumedLabel = 'Breathing resumed after a pause. Please check on them.';
    for (let i = 0; i < n; i++) {
      const t = trk.t[i], per = trk.base_period[i], ps = trk.pause_s[i], qu = trk.quiet[i], sn = trk.pause_snr[i];
      const recentLow = !!(trk.recent_low && trk.recent_low[i]);
      const gated = !!(trk.recent_gated && trk.recent_gated[i]);
      const need = Number.isFinite(per) ? Math.max(pauseMinS, per) : pauseMinS;
      const wq = need + 10.0;
      const noSwing = Number.isFinite(ps) && ps >= need;
      const armed = Number.isFinite(sn) && sn >= minPauseSnr;
      const rn = armed ? 1.0 / sn : NaN;
      const qThr = armed ? Math.min(0.75, Math.max(0.3, Math.hypot(1.0 - need / wq, rn))) : NaN;
      const quietNow = armed && Number.isFinite(qu) && qu < qThr && (t - lastResume) >= wq;
      quietRun = quietNow ? quietRun + 1 : 0;
      const bandQuiet = quietRun >= quietPersist;
      const tauBand = armed && Number.isFinite(qu) ? Math.min(wq, Math.max(0, wq * (1.0 - Math.sqrt(Math.max(0, qu * qu - rn * rn))))) : NaN;
      const cands = [ps, tauBand].filter((v) => Number.isFinite(v));
      const est = cands.length ? Math.max.apply(null, cands) : NaN;
      pauseEst[i] = est;
      const low = noSwing || bandQuiet;
      let lvl, why, wkey;
      if (low && !latched && (t - lastRateT) <= wq) {
        latched = true; latchT0 = t; latchEst0 = Math.max(Number.isFinite(est) ? est : need, need);
      }
      if (latched && trk.motion[i]) { latched = false; quietRun = 0; }
      if (latched) {
        let back;
        if (!Number.isFinite(ps)) back = !!trk.reliable[i];
        else {
          const bandBack = !armed || !Number.isFinite(qu) || qu > Math.min(0.95, qThr + 0.25);
          const swingBack = Number.isFinite(sn) && sn >= swingResumeSnr && Number.isFinite(per) && ps < 1.5 * per;
          back = !noSwing && (bandBack || swingBack);
        }
        if (back) { latched = false; resumedUntil = t + 30.0; lastResume = t; quietRun = 0; }
        else { lvl = 'urgent'; why = pauseLabel; wkey = 'pause'; pauseEst[i] = Math.max(Number.isFinite(est) ? est : 0, latchEst0 + (t - latchT0)); }
      }
      if (!latched) {
        if (trk.motion[i]) { lvl = 'moving'; why = 'Movement detected. Reading paused.'; wkey = 'moving'; }
        else if (trk.reliable[i]) {
          smooth = smooth.concat([trk.bpm[i]]).slice(-3);
          const c = classifyRate(median(smooth), cfg.profile);
          lvl = c[0]; why = c[1]; wkey = c[2];
          lastGood = t;
          if (t <= resumedUntil && STATUS_ORDER[lvl] < STATUS_ORDER.watch) { lvl = 'watch'; why = resumedLabel; wkey = 'resumed'; }
          else if (!armed && Number.isFinite(sn)) { why = why + ' (pause check limited: weak signal)'; wkey = wkey + '+weak'; }
        } else if (t <= resumedUntil) { lvl = 'watch'; why = resumedLabel; wkey = 'resumed'; }
        else if ((t - lastGood) <= noReadAfter && (current === 'typical' || current === 'watch') && curReason !== resumedLabel && !recentLow) {
          lvl = current; why = curReason; wkey = curKey;
        } else { lvl = 'no_reading'; why = 'No reliable reading. Count breaths for 60 s.'; wkey = 'noread'; }
      }
      if (lvl === current) { pending = null; pendingN = 0; curReason = why; curKey = wkey; }
      else {
        const immediate = (lvl === 'urgent' && why === pauseLabel) || lvl === 'moving' || current === 'moving';
        if (pending === lvl) pendingN++; else { pending = lvl; pendingN = 1; }
        if (immediate || pendingN >= persistHops) { current = lvl; curReason = why; curKey = wkey; pending = null; pendingN = 0; }
      }
      status.push(current); reason.push(curReason); key.push(curKey);
      // breathing counts as seen when a rate-based state is shown, or when the window held clear breathing that has since gone quiet
      if (((current === 'typical' || current === 'watch' || current === 'urgent') && curReason !== pauseLabel && curReason !== resumedLabel) || gated) lastRateT = t;
    }
    return { status, reason, key, pause_est: pauseEst };
  }

  // ------------------------------------------------------------------ link health
  function linkHealth(L) {
    const t = L.t, n = t.length;
    let lost = 0;
    for (let i = 1; i < n; i++) lost += Math.max(0, L.seq[i] - L.seq[i - 1] - 1);
    const sent = L.seq[n - 1] - L.seq[0] + 1;
    const dts = [];
    for (let i = 1; i < n; i++) dts.push(t[i] - t[i - 1]);
    const slots = validSlots(L.fwi);
    let steps = 0;
    let prevDb = null;
    for (let i = 0; i < n; i++) {
      let ss = 0;
      for (const s of slots) ss += L.H[i].re[s] * L.H[i].re[s] + L.H[i].im[s] * L.H[i].im[s];
      const db = 20 * Math.log10(Math.sqrt(ss / slots.length) + 1e-9);
      if (prevDb !== null && Math.abs(db - prevDb) > 1.5) steps++;
      prevDb = db;
    }
    const rs = Array.from(L.rssi);
    const rm = rs.reduce((a, b) => a + b, 0) / n;
    return {
      sensor: L.label, mac: L.mac, packets: n, duration_s: t[n - 1] - t[0],
      rate_hz: (n - 1) / Math.max(t[n - 1] - t[0], 1e-9), loss_pct: 100 * lost / Math.max(sent, 1), lost_packets: lost,
      max_gap_ms: 1000 * Math.max.apply(null, dts), median_interval_ms: 1000 * median(dts),
      rssi_mean_dbm: rm, gain_step_pct: 100 * steps / Math.max(n - 1, 1), channel: L.channel, valid_subcarriers: slots.length,
    };
  }

  function analyzeSession(S, profiles, cfgOverride) {
    let tEnd = Infinity;
    for (const m of S.macs) tEnd = Math.min(tEnd, S.links[m].t[S.links[m].t.length - 1]);
    const tracks = {}, features = {}, health = {};
    for (const m of S.macs) {
      const cfg = Object.assign(defaultConfig((profiles && profiles[m]) || 'adult'), cfgOverride || {});
      const F = linkFeatures(S.links[m], cfg.fs, tEnd);
      features[m] = F;
      tracks[m] = F.T >= Math.round(cfg.win_s * cfg.fs) ? trackLink(F, cfg) : null;
      health[m] = linkHealth(S.links[m]);
    }
    return { tracks, features, health, tEnd };
  }


  // ------------------------------------------------------------------ live streaming (USB serial)
  /* Incremental version of trackLink for a live stream. Every hop (2 s of receiver time) it
   * recomputes features over the trailing `keepS` seconds, estimates the newest window, carries
   * the pause detector and baseline across hops, and re-runs the screening state machine over the
   * accumulated per-hop history. Results match the file pipeline closely but not bit-for-bit
   * (the causal filter restarts at the buffer start; movement normalisation uses running medians).
   */
  class LiveSession {
    constructor(profiles) {
      this.profiles = profiles || {};
      this.links = new Map();
      this.t0us = null;
      this.keepS = 75;
      this.packets = 0;
      this.bad = 0;
    }
    setProfile(mac, profile) { this.profiles[mac] = profile; const L = this.links.get(mac); if (L) { L.cfg = defaultConfig(profile); L.hist = newHist(); L.base = null; L.swing = null; } }
    pushLine(line) {
      const r = parseLine(line);
      if (!r || r.len !== 128) { this.bad++; return null; }
      return this.push(r);
    }
    push(r) {
      let L = this.links.get(r.mac);
      if (!L) {
        L = { mac: r.mac, label: 'Sensor ' + (this.links.size + 1), recs: [], tsAdd: 0, tsPrev: null, seqAdd: 0, seqPrev: null,
          cfg: defaultConfig(this.profiles[r.mac] || 'adult'), hist: newHist(), base: null, swing: null, lastT: null,
          nextTick: null, rsdHist: [], decHist: [], fwi: r.fwi, channel: r.channel, lost: 0, steps: 0, prevDb: null };
        this.links.set(r.mac, L);
      }
      if (L.tsPrev !== null && r.ts_us - L.tsPrev < -TS_WRAP / 2) L.tsAdd += TS_WRAP;
      L.tsPrev = r.ts_us;
      const tsU = r.ts_us + L.tsAdd;
      if (this.t0us === null) this.t0us = tsU;
      if (L.seqPrev !== null) {
        let ds = r.seq - L.seqPrev;
        if (ds < -SEQ_WRAP / 2) ds += SEQ_WRAP;
        if (ds > 1) L.lost += ds - 1;
      }
      L.seqPrev = r.seq;
      const t = (tsU - this.t0us) / 1e6;
      const re = new Float64Array(64), im = new Float64Array(64);
      for (let s = 0; s < 64; s++) { im[s] = r.raw[2 * s]; re[s] = r.raw[2 * s + 1]; }
      if (r.fwi) { re[0] = re[1] = NaN; im[0] = im[1] = NaN; }
      L.recs.push({ t, rssi: r.rssi, H: { re, im } });
      // drop records outside the buffer
      while (L.recs.length && L.recs[0].t < t - this.keepS - 5) L.recs.shift();
      this.packets++;
      if (L.nextTick === null) L.nextTick = t + L.cfg.win_s;
      if (t >= L.nextTick && L.recs.length > 30) {
        const res = this.tick(L, t);
        L.nextTick += L.cfg.hop_s;
        while (L.nextTick <= t) L.nextTick += L.cfg.hop_s;
        return res;
      }
      return null;
    }
    tick(L, tNow) {
      const cfg = L.cfg, fs = cfg.fs;
      const recs = L.recs.filter((x) => x.t >= tNow - this.keepS);
      const link = { mac: L.mac, label: L.label, t: Float64Array.from(recs.map((x) => x.t)), rssi: Float64Array.from(recs.map((x) => x.rssi)),
        H: recs.map((x) => x.H), fwi: L.fwi, channel: L.channel };
      if (link.t.length < 2 || link.t[link.t.length - 1] - link.t[0] < cfg.win_s) return null;
      const opts = {};
      if (L.rsdHist.length > 200) { opts.medRssiSd = median(L.rsdHist); opts.medDec = median(L.decHist); }
      const F = linkFeatures(link, fs, undefined, opts);
      // remember new samples for the running medians (last 5 minutes)
      const newFrom = L.lastT === null ? 0 : searchsortedLeft(F.t, L.lastT + 1e-9);
      for (let i = newFrom; i < F.T; i++) { L.rsdHist.push(F.rsd[i]); L.decHist.push(F.dec[i]); }
      const cap = Math.round(300 * fs);
      if (L.rsdHist.length > cap) { L.rsdHist.splice(0, L.rsdHist.length - cap); L.decHist.splice(0, L.decHist.length - cap); }
      const T = F.T, Cn = F.Cn;
      const nw = Math.round(cfg.win_s * fs), nTail = Math.round(6 * fs), thr = 1.0, k = Math.max(1, Math.round(fs));
      const act = new Float64Array(T), off = (k - 1) >> 1;
      for (let i = 0; i < T; i++) { let s = 0; for (let j = 0; j < k; j++) { const idx = i + off - j; if (idx >= 0 && idx < T) s += F.activity[idx]; } act[i] = s / k; }
      const fc = bandSOS(cfg, fs);
      const nRef = Math.min(Math.round(5 * fs), T);
      const Xc = new Float64Array(T * Cn), colb = new Float64Array(T);
      for (let c = 0; c < Cn; c++) {
        let m = 0; for (let i = 0; i < nRef; i++) m += F.X[i * Cn + c]; m /= nRef;
        for (let i = 0; i < T; i++) colb[i] = F.X[i * Cn + c] - m;
        const y = sosfilt1(fc.sos, colb, null).y;
        for (let i = 0; i < T; i++) Xc[i * Cn + c] = y[i];
      }
      const proj = (lo, hi, b) => { const r = new Float64Array(hi - lo); for (let i = lo; i < hi; i++) { let s = 0; for (let j = 0; j < b.keep.length; j++) { const c = b.keep[j]; s += (Xc[i * Cn + c] / b.sd[c]) * b.w[j]; } r[i - lo] = s; } return r; };
      const e = T;
      let s0 = e - nw;
      let movingNow = false;
      for (let i = e - nTail; i < e; i++) if (act[i] > thr) { movingNow = true; break; }
      let lastHot = -1;
      for (let i = s0; i < e; i++) if (act[i] > thr) lastHot = i - s0;
      let contaminated = false;
      if (lastHot >= 0) { const sClean = s0 + lastHot + Math.round(fs) + 1; if (e - sClean >= Math.round(cfg.min_clean_s * fs)) s0 = sClean; else contaminated = true; }
      const prevIdx = L.lastT === null ? s0 : Math.max(0, searchsortedLeft(F.t, L.lastT + 1e-9));
      let movedSince = false;
      for (let i = prevIdx; i < e; i++) if (act[i] > thr) { movedSince = true; break; }
      if (movedSince) { L.base = null; L.swing = null; }
      const pauseMin = cfg.profile === 'adult' ? 10.0 : 20.0;
      let pauseS = NaN, quiet = NaN;
      if (L.base && L.swing) {
        const p = proj(prevIdx, e, L.base);
        for (let i = 0; i < p.length; i++) L.swing.update(F.t[prevIdx + i], p[i]);
        pauseS = F.t[e - 1] - L.swing.last_t;
        // v1.3.1: equal-weight band amplitude over need + 10 s, never reaching back before the baseline's first sample
        const need = Math.max(pauseMin, L.base.period), nQ = roundHalfEven((need + 10.0) * fs);
        if (e - nQ >= 0 && F.t[e - nQ] >= L.base.startT - 1e-9) quiet = narrowbandAmp(proj(e - nQ, e, L.base), fs, L.base.f, 0.05, true) / (L.base.nb + 1e-12);
      }
      L.lastT = F.t[e - 1];
      let gapSum = 0; for (let i = s0; i < e; i++) gapSum += F.gap[i];
      const gapFrac = gapSum / (e - s0);
      const r = estimateWindow(F, s0, e, cfg);
      const q = Math.min(1, Math.max(0, 0.5 * (r.prominence / 0.6) + 0.5 * (r.acf / 0.7)));
      const periodic = r.agree && r.prominence >= cfg.min_prominence && r.acf >= cfg.min_acf && !contaminated && gapFrac <= cfg.max_gap_frac;
      const rr = recentRatio(r.waveform, fs, r.bpm_spec, cfg.recent_s);
      const recentLow = Number.isFinite(rr) && rr < cfg.recent_min_ratio;
      const reliable = periodic && !recentLow;
      if (periodic) {
        const pc = proj(s0, e, { keep: r.keep, sd: r.sd, w: r.weights });
        const winRms = stdPop(pc, Math.round(3 * fs), pc.length);
        const tailRms = stdPop(pc, Math.max(0, pc.length - Math.round(pauseMin * fs)), pc.length);
        if (!L.base || tailRms >= 0.6 * winRms) {
          const amp = Math.SQRT2 * winRms, fresh = !L.base;
          const fB = Math.max(r.bpm_spec, 1.0) / 60.0;
          const nR = roundHalfEven((Math.max(pauseMin, 1.0 / fB) + 10.0) * fs);
          const ref = pc.subarray(Math.max(0, pc.length - nR));
          const nbSig = narrowbandAmp(ref, fs, fB, 0.05, true);
          const band = PROFILES[cfg.profile].band;
          const offs = [fB - 0.30, fB - 0.20, fB + 0.20, fB + 0.30].filter((f) => f >= band[0] && f <= band[1]);
          const nbNoise = offs.length ? median(offs.map((f) => narrowbandAmp(ref, fs, f, 0.0, true))) : NaN;
          L.base = { keep: r.keep, sd: r.sd, w: r.weights, amp, rms: winRms, sinceT: fresh ? F.t[e - 1] : L.base.sinceT,
            startT: fresh ? F.t[s0] : L.base.startT, period: 1.0 / fB, f: fB, nb: nbSig,
            snr: Number.isFinite(nbNoise) ? nbSig / (nbNoise + 1e-12) : NaN };
          if (fresh || !L.swing) L.swing = new SwingCounter(0.8 * amp, F.t[e - 1], pc[pc.length - 1]);
          else { L.swing.h = 0.8 * amp; L.swing.reset(pc[pc.length - 1]); }
        }
      }
      const H = L.hist;
      H.t.push(F.t[e - 1]); H.bpm.push(reliable ? r.bpm_spec : NaN); H.bpm_raw.push(r.bpm_spec); H.reliable.push(reliable);
      H.motion.push(movingNow); H.pause_s.push(pauseS); H.quiet.push(quiet); H.pause_snr.push(L.base ? L.base.snr : NaN);
      H.base_period.push(L.base ? L.base.period : NaN); H.quality.push(contaminated ? 0 : q); H.recent_low.push(recentLow); H.recent_gated.push(periodic && recentLow);
      const sf = screeningFlags(H, cfg);
      const w = r.waveform, sdw = stdPop(w) + 1e-12;
      const wave = Array.from(w.subarray(Math.max(0, w.length - 300))).map((v) => v / sdw);
      return { mac: L.mac, label: L.label, t: F.t[e - 1], status: sf.status[sf.status.length - 1], reason: sf.reason[sf.reason.length - 1],
        key: sf.key[sf.key.length - 1], bpm: reliable ? r.bpm_spec : NaN, raw: r.bpm_spec, quality: contaminated ? 0 : q, reliable, motion: movingNow,
        pause: sf.pause_est[sf.pause_est.length - 1], snr: L.base ? L.base.snr : NaN, wave, rssi: F.rssi[T - 1], activity: F.activity[T - 1], lost: L.lost, profile: cfg.profile };
    }
  }
  function newHist() { return { t: [], bpm: [], bpm_raw: [], reliable: [], motion: [], pause_s: [], quiet: [], pause_snr: [], base_period: [], quality: [], recent_low: [], recent_gated: [] }; }

  const api = { parseLine, parseText, buildSession, validSlots, linkFeatures, trackLink, estimateWindow, screeningFlags,
    classifyRate, analyzeSession, linkHealth, defaultConfig, PROFILES, butterBandpassSOS, sosfiltZi, STATUS_ORDER, LiveSession };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.HinigramDSP = api;
})(typeof window !== 'undefined' ? window : this);
