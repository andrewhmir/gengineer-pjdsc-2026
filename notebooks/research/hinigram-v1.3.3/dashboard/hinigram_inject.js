/* Hinigram injection bench: adds known breathing (and, on request, simulated movement) to real ESP32 CSI packets while
 * they stream, so the board can be tested live against a known truth.
 *
 * The breathing model is hinigram_live.inject_breathing's: amplitude and phase modulation on the 52 LLTF data
 * subcarriers, 30% of it common to all of them and the rest a smooth random pattern across them; breath-to-breath rate
 * variability; inhale/exhale asymmetry; soft pause edges; values re-quantised to int8; every header field kept. Python
 * computes the waveform for a whole file at once; here it runs forward in time (20 Hz grid, trailing instead of centred
 * smoothing), so the rate, depth, pauses and movement can be changed while it plays. One deliberate difference: after a
 * pause breathing resumes at the person's rate behind the 1.5 s soft edge, where Python's rate also ramps up from zero.
 * Its random draws come from its own generator, so a run here is not the same realisation as a Python run with the same
 * seed. The truth it records is what was actually injected, which is what the board is scored against.
 *
 * Runs in the board's worker and in Node (tests). No DOM.
 */
(function (root) {
  'use strict';
  const TS_WRAP = 4294967296, SEQ_WRAP = 65536;
  const SUB = (s) => (s < 32 ? s : s - 64);                 // ESP32 slot order: subcarriers 0..31, then -32..-1
  const DATA = new Uint8Array(64);                           // the 52 LLTF data slots (1..26 and 38..63)
  for (let s = 1; s <= 26; s++) DATA[s] = 1;
  for (let s = 38; s <= 63; s++) DATA[s] = 1;
  const GRID = 0.05;                                         // breathing_waveform's 20 Hz grid
  const W_NORM = 1.169;                                      // 95th percentile of |sin p + 0.25 sin(2p + 0.6)|: Python's normalisation
  const TRUTH_EVERY = 5;                                     // record the truth every 5 grid steps (4 Hz)
  const DEFAULTS = { bpm: 16, depth: 0.05, phaseDepth: null, commonMode: 0.3, jitter: 0.04 };

  // ------------------------------------------------------------------ seeded random numbers (mulberry32)
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(u) { let x = 0; while (x === 0) x = u(); return Math.sqrt(-2 * Math.log(x)) * Math.cos(2 * Math.PI * u()); }
  function roundHalfEven(x) { const r = Math.round(x); return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r; }
  const clip8 = (v) => (v > 127 ? 127 : v < -127 ? -127 : v);

  // ------------------------------------------------------------------ breathing, generated forward in time
  /** One person's breathing. mode: 'breathing' (at bpm), 'hold' (a pause: nobody breathes, truth 0) or 'empty'
   *  (nobody there: no breathing and no truth). A script, [[t0, t1, bpm], ...] in seconds from scriptT0 with bpm 0
   *  for a pause, overrides the mode and rate until it is cleared; after its last segment the last rate holds. */
  class Breather {
    constructor(seed) {
      this.u = rng(seed);
      this.bpm = DEFAULTS.bpm; this.mode = 'breathing'; this.jitter = DEFAULTS.jitter;
      this.script = null; this.scriptT0 = 0;
      this.tg = null; this.n = 0;
      this.phase = 2 * Math.PI * this.u();
      this.walk = gauss(this.u) * this.jitter;               // rate variability: Ornstein-Uhlenbeck, 25 s, SD = jitter
      this.ampN = 0;                                          // breath size variability: OU, 10 s, SD 0.019 (Python's level)
      this.r4 = new Float64Array(80); this.s4 = 0;            // trailing 4 s mean of the target rate (Python: 4 s box)
      this.r15 = new Float64Array(30); this.s15 = 0;          // trailing 1.5 s presence: the soft pause edges
      this.k = 0; this.prev = 0; this.cur = 0;
      this.truth = { t: [], bpm: [] };
      this.truthNow = null;
    }
    /** The programmed rate and presence at time t. During a pause the rate keeps its last value (the pause is made by
     *  the presence gate alone), so breathing resumes at the person's rate after a 1.5 s soft edge. Python's file model
     *  sets the rate to 0 during pauses, so its rate also ramps up from zero over 4 s after each pause. */
    target(t) {
      if (this.script && this.script.length) {
        const x = t - this.scriptT0;
        let seg = this.script[this.script.length - 1];
        for (const s of this.script) if (x >= s[0] && x < s[1]) { seg = s; break; }
        if (x < this.script[0][0]) seg = this.script[0];
        if (seg[2] > 0) { this.lastRate = seg[2]; return { bpm: seg[2], present: 1, there: 1 }; }
        return { bpm: this.lastRate || this.bpm, present: 0, there: 1 };
      }
      if (this.mode === 'breathing' && this.bpm > 0) { this.lastRate = this.bpm; return { bpm: this.bpm, present: 1, there: 1 }; }
      return { bpm: this.lastRate || this.bpm || 16, present: 0, there: this.mode === 'empty' ? 0 : 1 };
    }
    _start(t) {
      const g = this.target(t);
      this.r4.fill(g.bpm); this.s4 = g.bpm * this.r4.length;
      this.r15.fill(g.present); this.s15 = g.present * this.r15.length;
      this.tg = t; this.cur = this._wave(g); this.prev = this.cur;
    }
    _wave(g) {
      const bpmS = this.s4 / this.r4.length, gate = this.s15 / this.r15.length;
      const f = (bpmS / 60) * (1 + this.walk);
      this.fInst = f; this.present = g.present; this.there = g.there;
      const w = Math.sin(this.phase) + 0.25 * Math.sin(2 * this.phase + 0.6);
      return (w * (1 + this.ampN) * gate) / W_NORM;
    }
    _step() {
      const t = this.tg + GRID, g = this.target(t), u = this.u;
      const k = this.k % this.r4.length, j = this.k % this.r15.length;
      this.s4 += g.bpm - this.r4[k]; this.r4[k] = g.bpm;
      this.s15 += g.present - this.r15[j]; this.r15[j] = g.present;
      this.k++;
      const aW = GRID / 25, aA = GRID / 10;
      this.walk += -aW * this.walk + this.jitter * Math.sqrt(2 * aW) * gauss(u);
      this.ampN += -aA * this.ampN + 0.019 * Math.sqrt(2 * aA) * gauss(u);
      const bpmS = this.s4 / this.r4.length, gate = this.s15 / this.r15.length;
      if (gate > 0) this.phase += 2 * Math.PI * (bpmS / 60) * (1 + this.walk) * GRID;
      if (this.phase > 2e4) this.phase -= 2 * Math.PI * Math.floor(this.phase / (2 * Math.PI));
      this.prev = this.cur; this.tg = t; this.cur = this._wave(g);
      // truth, as hinigram_live.breathing_waveform returns it: the instantaneous rate where breathing is present, else 0;
      // null when the chair is empty or nothing is being added to its packets
      this.truthNow = !this.there || this.silent ? null : this.present ? this.fInst * 60 : 0;
      if (++this.n % TRUTH_EVERY === 0) { this.truth.t.push(Math.round(t * 100) / 100); this.truth.bpm.push(this.truthNow === null ? null : Math.round(this.truthNow * 100) / 100); }
    }
    /** Breathing waveform at time t (seconds, never decreasing), roughly within [-1, 1]. */
    at(t) {
      if (this.tg === null) this._start(t);
      while (this.tg < t) this._step();
      const w = (t - (this.tg - GRID)) / GRID;               // linear interpolation between the last two grid points
      return this.prev + (this.cur - this.prev) * Math.min(1, Math.max(0, w));
    }
    takeTruth() { const out = this.truth; this.truth = { t: [], bpm: [] }; return out; }
  }

  // ------------------------------------------------------------------ one chair: breathing + movement on its packets
  class ChairInjector {
    constructor(seed, params) {
      this.seed = seed;
      this.br = new Breather(seed);
      this.on = true;
      Object.assign(this, { depth: DEFAULTS.depth, phaseDepth: DEFAULTS.phaseDepth, commonMode: DEFAULTS.commonMode });
      // the chair's own pattern across subcarriers (inject_breathing: cos(pi c kk + theta), c in [0.6, 1.6])
      const u = rng(seed * 7919 + 13);
      const th1 = 2 * Math.PI * u(), th2 = 2 * Math.PI * u(), c1 = 0.6 + u(), c2 = 0.6 + u();
      this.diffA = new Float64Array(64); this.wp = new Float64Array(64);
      for (let s = 0; s < 64; s++) {
        const kk = SUB(s) / 26;
        this.diffA[s] = Math.cos(Math.PI * c1 * kk + th1);
        this.wp[s] = Math.cos(Math.PI * c2 * kk + th2);
      }
      // movement: a fast-changing reshaping of the channel across subcarriers plus RSSI swings
      this.mv = { c3: 0.8 + u(), c4: 0.8 + u(), p3: 2 * Math.PI * u(), p4: 2 * Math.PI * u(), pr: 2 * Math.PI * u(), spans: [] };
      this.set(params || {});
    }
    set(p) {
      if (p.depth !== undefined) this.depth = Math.max(0, Math.min(0.2, +p.depth));
      if (p.phaseDepth !== undefined) this.phaseDepth = p.phaseDepth === null ? null : +p.phaseDepth;
      if (p.on !== undefined) this.on = !!p.on;
      if (p.bpm !== undefined) this.br.bpm = Math.max(0, +p.bpm);
      if (p.mode !== undefined) this.br.mode = p.mode;
      if (p.jitter !== undefined) this.br.jitter = Math.max(0, +p.jitter);
      if (p.script !== undefined) { this.br.script = p.script; if (p.scriptT0 !== undefined) this.br.scriptT0 = +p.scriptT0; }
    }
    /** Simulated movement (someone shifting in the seat) from t0 for dur seconds. */
    move(t0, dur) { this.mv.spans.push([t0, t0 + dur]); if (this.mv.spans.length > 20) this.mv.spans.shift(); }
    moveEnv(t) {
      let e = 0;
      for (const [a, b] of this.mv.spans) {
        if (t < a - 0.01 || t > b + 0.5) continue;
        const ramp = Math.min(1, (t - a) / 0.5, (b + 0.5 - t) / 0.5);
        e = Math.max(e, Math.max(0, ramp));
      }
      return e;
    }
    /** Modulate one packet at receiver time t. raw: 128 CSI values (imaginary first). Returns {raw: Int16Array, rssi}. */
    apply(raw, t, fwi, rssi) {
      this.br.silent = !this.on;
      const b = this.br.at(t);                                // always advanced, so the truth keeps time
      const bt = this.on ? b : 0;
      const me = this.on ? this.moveEnv(t) : 0;              // nothing at all is added to a chair that is off
      const out = new Int16Array(128);
      if (bt === 0 && me === 0) { out.set(raw.subarray ? raw.subarray(0, 128) : raw.slice(0, 128)); return { raw: out, rssi }; }
      const d = this.depth, pd = this.phaseDepth === null ? this.depth : this.phaseDepth, cm = this.commonMode;
      const M = this.mv, th3 = M.p3 + 2 * Math.PI * 0.9 * t + 1.6 * Math.sin(2 * Math.PI * 0.37 * t), th4 = M.p4 + 2 * Math.PI * 1.3 * t;
      for (let s = 0; s < 64; s++) {
        const im = raw[2 * s], re = raw[2 * s + 1];
        if (!DATA[s] || (fwi && s < 2)) { out[2 * s] = im; out[2 * s + 1] = re; continue; }
        const kk = SUB(s) / 26;
        let a = 1 + d * (cm + (1 - cm) * this.diffA[s]) * bt, ph = pd * this.wp[s] * bt;
        if (me > 0) { a *= 1 + 0.45 * me * Math.cos(Math.PI * M.c3 * kk + th3); ph += 0.8 * me * Math.cos(Math.PI * M.c4 * kk + th4); }
        const c = Math.cos(ph) * a, sn = Math.sin(ph) * a;
        const r2 = re * c - im * sn, i2 = re * sn + im * c;
        out[2 * s] = clip8(roundHalfEven(i2)); out[2 * s + 1] = clip8(roundHalfEven(r2));
      }
      if (fwi) for (let i = 0; i < 4; i++) out[i] = raw[i];
      const r = me > 0 ? rssi + Math.round(5 * me * Math.sin(2 * Math.PI * 0.8 * t + M.pr) + 2 * me * Math.sin(2 * Math.PI * 2.3 * t)) : rssi;
      return { raw: out, rssi: r };
    }
  }

  // ------------------------------------------------------------------ the packed format sample
  /** Parse the packed sample (pack_sample.py) once it is gunzipped. */
  function unpackBuffer(buf) {
    const u8 = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
    const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    if (String.fromCharCode(u8[0], u8[1], u8[2], u8[3]) !== 'HGS1') throw new Error('not a packed Hinigram sample');
    const hl = dv.getUint32(4, true);
    const head = JSON.parse(new TextDecoder().decode(u8.subarray(8, 8 + hl)));
    const n = head.n;
    let o = 8 + hl;
    const mi = u8.subarray(o, o + n); o += n;
    const rssi = new Int8Array(u8.buffer, u8.byteOffset + o, n); o += n;
    const seq = new Uint32Array(n), ts = new Uint32Array(n);
    for (let i = 0; i < n; i++) seq[i] = dv.getUint32(o + 4 * i, true);
    o += 4 * n;
    for (let i = 0; i < n; i++) ts[i] = dv.getUint32(o + 4 * i, true);
    o += 4 * n;
    const csi = new Int8Array(u8.buffer, u8.byteOffset + o, n * 128);
    const c = head.const, recs = [];
    for (let i = 0; i < n; i++) {
      recs.push({ mac: head.macs[mi[i]], rssi: rssi[i], seq: seq[i], ts_us: ts[i], noise_floor: c.noise_floor, channel: c.channel,
        sig_len: c.sig_len, rx_state: c.rx_state, len: c.len, fwi: c.first_word_invalid === 1, raw: Int16Array.from(csi.subarray(128 * i, 128 * i + 128)) });
    }
    return { file: head.file, macs: head.macs, t_host0: head.t_host0, recs };
  }
  /** Decode the base64 + gzip blob embedded in the board (browsers and workers with DecompressionStream). */
  async function unpackSample(b64) {
    const bin = atob(b64.replace(/\s+/g, ''));
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    const ds = new Blob([u8]).stream().pipeThrough(new DecompressionStream('gzip'));
    return unpackBuffer(new Uint8Array(await new Response(ds).arrayBuffer()));
  }
  /** Records from a receiver CSV, through the board's own parser (HinigramDSP.parseLine). */
  function recordsFromText(text, parseLine) {
    const recs = [], macs = [];
    for (const ln of text.split(/\r?\n/)) {
      const r = parseLine(ln);
      if (!r || r.len !== 128) continue;
      if (!macs.includes(r.mac)) macs.push(r.mac);
      recs.push(r);
    }
    return { macs, recs };
  }

  // ------------------------------------------------------------------ background player
  /** Streams a recording's packets as if live, looping it back and forth (forward, then reversed, then forward...) so
   *  there is no jump in the channel where it repeats. Each chair replays one source link from its own start offset, under
   *  its own MAC, with the source's packet loss (sequence gaps) and timing kept. Times are seconds on a new receiver clock. */
  class Player {
    constructor(src, chairs, range) {
      this.chairs = chairs.map((c) => Object.assign({}, c));
      const links = new Map();
      for (const r of src.recs) { if (!links.has(r.mac)) links.set(r.mac, []); links.get(r.mac).push(r); }
      // receiver time of each packet, unwrapped, relative to the first packet of the recording
      let t0 = null;
      for (const [, list] of links) {
        let add = 0, prev = null;
        for (const r of list) {
          if (prev !== null && r.ts_us - prev < -TS_WRAP / 2) add += TS_WRAP;
          prev = r.ts_us; r._tu = r.ts_us + add;
          if (t0 === null || r._tu < t0) t0 = r._tu;
        }
      }
      let tEnd = 0;
      for (const [, list] of links) for (const r of list) { r._t = (r._tu - t0) / 1e6; tEnd = Math.max(tEnd, r._t); }
      const a = range ? Math.max(0, range[0]) : 0, b = range ? Math.min(tEnd, range[1]) : tEnd;
      this.a = a; this.D = b - a;
      if (!(this.D > 5)) throw new Error('the background is shorter than 5 seconds');
      this.links = new Map();
      for (const [m, list] of links) this.links.set(m, list.filter((r) => r._t >= a && r._t <= b));
      this.chairs.forEach((c) => {
        // a start point given as a fraction of the forward-and-back cycle (when the caller does not know its length)
        if (c.offset === undefined && c.offsetFrac !== undefined) c.offset = c.offsetFrac * 2 * this.D;
        const L = this.links.get(c.src);
        if (!L || L.length < 10) throw new Error('no packets for ' + c.src);
        c.L = L; c.cycle = Math.floor((c.offset || 0) / this.D);
        const pos = (c.offset || 0) - c.cycle * this.D;
        c.fwd = c.cycle % 2 === 0;
        c.i = c.fwd ? L.findIndex((r) => r._t - a >= pos) : L.length - 1 - L.slice().reverse().findIndex((r) => this.D - (r._t - a) >= pos);
        if (c.i < 0 || c.i >= L.length) c.i = c.fwd ? 0 : L.length - 1;
        c.seqOut = (c.seqStart || 1) % SEQ_WRAP; c.lastSrcSeq = null; c.emitted = 0;
      });
    }
    _time(c, r) { const p = r._t - this.a; return c.cycle * this.D + (c.fwd ? p : this.D - p) - (c.offset || 0); }
    /** Every packet with output time <= u, in time order: [{chair, src, u, seq}] */
    until(u) {
      const out = [];
      for (const c of this.chairs) {
        for (;;) {
          const r = c.L[c.i], tu = this._time(c, r);
          if (tu > u) break;
          if (c.lastSrcSeq !== null) { let ds = Math.abs(r.seq - c.lastSrcSeq); if (ds > SEQ_WRAP / 2) ds = SEQ_WRAP - ds; c.seqOut = (c.seqOut + Math.max(1, Math.min(ds, 1000))) % SEQ_WRAP; }
          c.lastSrcSeq = r.seq;
          out.push({ chair: c, src: r, u: Math.max(0, tu), seq: c.seqOut });
          c.emitted++;
          // at either end the direction turns without repeating the end packet
          if (c.fwd) { if (++c.i >= c.L.length) { c.i = c.L.length - 2; c.cycle++; c.fwd = false; c.lastSrcSeq = null; } }
          else if (--c.i < 0) { c.i = 1; c.cycle++; c.fwd = true; c.lastSrcSeq = null; }
        }
      }
      out.sort((x, y) => x.u - y.u);
      return out;
    }
  }

  // ------------------------------------------------------------------ CSV lines in the receiver's own layout
  const CONST_HDR = { rate: 11, sig_mode: 1, mcs: 0, bandwidth: 0, smoothing: 1, not_sounding: 1, aggregation: 0, stbc: 0, fec_coding: 0, sgi: 0,
    noise_floor: -96, ampdu_cnt: 0, channel: 6, secondary_channel: 0, ant: 0, sig_len: 47, rx_state: 1 };
  /** One CSI_DATA line with a host timestamp in front, as firmware/tools/log_serial.py writes them. */
  function formatLine(tHost, r) {
    const h = Object.assign({}, CONST_HDR, r);
    return tHost.toFixed(6) + ',CSI_DATA,' + r.seq + ',' + r.mac + ',' + r.rssi + ',' + h.rate + ',' + h.sig_mode + ',' + h.mcs + ',' + h.bandwidth + ',' +
      h.smoothing + ',' + h.not_sounding + ',' + h.aggregation + ',' + h.stbc + ',' + h.fec_coding + ',' + h.sgi + ',' + h.noise_floor + ',' + h.ampdu_cnt + ',' +
      h.channel + ',' + h.secondary_channel + ',' + r.ts_us + ',' + h.ant + ',' + h.sig_len + ',' + h.rx_state + ',128,' + (r.fwi ? 1 : 0) + ',"[' + Array.prototype.join.call(r.raw, ',') + ']"';
  }
  /** Replace only the CSI values of a received line (the header stays verbatim, as inject_breathing does). */
  function replaceCsi(line, raw) {
    const b = line.indexOf('['), e = line.lastIndexOf(']');
    return line.slice(0, b + 1) + Array.prototype.join.call(raw, ',') + line.slice(e);
  }

  /** Python's truth_on_grid for one trailing window: mean true rate if breathing fills at least 80% of it, else null. */
  function windowTruth(T, tEnd, winS) {
    let n = 0, pres = 0, sum = 0, empty = 0;
    for (let i = T.t.length - 1; i >= 0; i--) {
      const t = T.t[i];
      if (t > tEnd) continue;
      if (t <= tEnd - winS) break;
      n++;
      const v = T.bpm[i];
      if (v === null) { empty++; continue; }
      if (v > 0) { pres++; sum += v; }
    }
    if (!n || n < winS * 2) return { full: false, bpm: null, n };   // not enough truth yet (4 Hz: 120 samples per 30 s)
    return { full: pres / n >= 0.8, bpm: pres ? sum / pres : null, n, empty: empty / n, present: pres / n };
  }

  const api = { Breather, ChairInjector, Player, unpackBuffer, unpackSample, recordsFromText, formatLine, replaceCsi, windowTruth,
    rng, DEFAULTS, TS_WRAP, SEQ_WRAP };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.HinigramInject = api;
})(typeof self !== 'undefined' ? self : typeof globalThis !== 'undefined' ? globalThis : this);
