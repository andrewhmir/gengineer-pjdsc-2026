/* Hinigram worker: runs the v1.3 DSP off the page's main thread.
 * Messages in:  {type:'analyze', text, name, profiles} | {type:'live-start', profiles} |
 *               {type:'live-lines', lines} | {type:'live-profile', mac, profile}
 * Messages out: {type:'result', data} | {type:'error', message} | {type:'live', updates, packets}
 * `data` has the same shape as the precomputed sources in dashboard_data.json.
 */
(function (G) {
  'use strict';
  const DSP = G.HinigramDSP;
  const SEATS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const rnd = (v, nd) => {
    if (v === null || v === undefined || typeof v !== 'number' || !Number.isFinite(v)) return null;
    const p = Math.pow(10, nd);
    return Math.round(v * p) / p;
  };
  const arr = (a, nd) => Array.from(a, (v) => rnd(v, nd));
  function lowerBound(a, x) { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < x) lo = m + 1; else hi = m; } return lo; }
  function interp(x, xp, fp) {
    const n = xp.length;
    if (!n) return NaN;
    if (x <= xp[0]) return fp[0];
    if (x >= xp[n - 1]) return fp[n - 1];
    const j = lowerBound(xp, x);
    const x0 = xp[j - 1], x1 = xp[j];
    return fp[j - 1] + (fp[j] - fp[j - 1]) * (x - x0) / (x1 - x0);
  }
  function movingAvg(a, k) {
    // centred moving average normalised by the samples actually inside the window
    const n = a.length, out = new Float64Array(n), off = k >> 1;
    for (let i = 0; i < n; i++) {
      let s = 0, c = 0;
      for (let j = i - off; j < i - off + k; j++) if (j >= 0 && j < n && Number.isFinite(a[j])) { s += a[j]; c++; }
      out[i] = c ? s / c : NaN;
    }
    return out;
  }
  function packetDb(H, slots) {
    let ss = 0;
    for (const s of slots) ss += H.re[s] * H.re[s] + H.im[s] * H.im[s];
    return 20 * Math.log10(Math.sqrt(ss / slots.length) + 1e-9);
  }
  function isoPH(epochS) {
    if (!Number.isFinite(epochS) || epochS < 1e9) return null; // not a wall-clock timestamp
    const d = new Date(epochS * 1000 + 8 * 3600e3);
    const p = (x, n) => String(x).padStart(n || 2, '0');
    return d.getUTCFullYear() + '-' + p(d.getUTCMonth() + 1) + '-' + p(d.getUTCDate()) + 'T' + p(d.getUTCHours()) + ':' +
      p(d.getUTCMinutes()) + ':' + p(d.getUTCSeconds()) + '.' + p(d.getUTCMilliseconds(), 3) + '+08:00';
  }

  /** Engineer series on a 2 Hz grid (same definitions as export_dashboard.py). */
  function series2hz(L, F, tEnd) {
    const slots = DSP.validSlots(L.fwi);
    const n = L.t.length;
    const cs = new Float64Array(n + 1);
    let prev = null;
    for (let i = 0; i < n; i++) {
      const db = packetDb(L.H[i], slots);
      cs[i + 1] = cs[i] + (prev !== null && Math.abs(db - prev) > 1.5 ? 1 : 0);
      prev = db;
    }
    const rssiSm = movingAvg(F.rssi, 10);
    const out = { t: [], rate: [], rssi: [], steps: [], act: [] };
    for (let t = 5.0; t < tEnd - 1e-9; t += 0.5) {
      const lo = lowerBound(L.t, t - 5.0), hi = lowerBound(L.t, t);
      out.t.push(rnd(t, 2));
      out.rate.push(rnd((hi - lo) / 5.0, 2));
      out.steps.push(rnd(((cs[hi] - cs[lo]) / Math.max(hi - lo, 1)) * 100, 1));
      out.rssi.push(rnd(interp(t, F.t, rssiSm), 1));
      out.act.push(rnd(interp(t, F.t, F.activity), 3));
    }
    return out;
  }

  function convertSession(S, A, name, profiles) {
    let packets = 0, short = false;
    const sensors = S.macs.map((m, i) => {
      const L = S.links[m], F = A.features[m], trk = A.tracks[m];
      packets += L.t.length;
      const prof = (profiles && profiles[m]) || 'adult';
      const cfg = DSP.defaultConfig(prof);
      const health = {};
      const h = A.health[m];
      for (const k of Object.keys(h)) health[k] = typeof h[k] === 'number' ? rnd(h[k], 3) : h[k];
      const d = { mac: m, label: 'Sensor ' + (i + 1), seat: SEATS[i] || String(i + 1), profile: prof, health,
        hops: { t: [], status: [], reason: [], bpm: [], raw: [], q: [], rel: [], mot: [], pause: [], snr: [] },
        wave: { t0: 0, fs: cfg.fs, v: [] }, series: series2hz(L, F, A.tEnd) };
      if (!trk) { short = true; return d; }
      d.hops = { t: arr(trk.t, 2), status: trk.status.slice(), reason: trk.reason.slice(), bpm: arr(trk.bpm, 2), raw: arr(trk.bpm_raw, 2),
        q: arr(trk.quality, 3), rel: trk.reliable.map(Boolean), mot: trk.motion.map(Boolean), pause: arr(trk.pause_est, 1), snr: arr(trk.pause_snr, 2) };
      const nw = Math.round(cfg.win_s * cfg.fs), nh = Math.round(cfg.hop_s * cfg.fs);
      const v = [];
      for (const seg of trk.wave) for (const x of seg) v.push(rnd(x, 3));
      d.wave = { t0: rnd(F.T >= nw ? F.t[nw - nh] : F.t[0], 3), fs: cfg.fs, v };
      return d;
    });
    return { file: name, title: name, note: '', duration: rnd(S.duration, 2), packets, start: isoPH(S.t0Host), sensors, short, bad: S.nBad };
  }

  /** Same steps as HinigramDSP.analyzeSession, reporting progress after each sensor. */
  function analyzeText(text, name, profiles, onProgress) {
    profiles = profiles || {};
    const S = DSP.parseText(text, name);
    let tEnd = Infinity;
    for (const m of S.macs) tEnd = Math.min(tEnd, S.links[m].t[S.links[m].t.length - 1]);
    const A = { tracks: {}, features: {}, health: {}, tEnd };
    if (onProgress) onProgress(0, S.macs.length);
    S.macs.forEach((m, i) => {
      const cfg = DSP.defaultConfig(profiles[m] || 'adult');
      const F = DSP.linkFeatures(S.links[m], cfg.fs, tEnd);
      A.features[m] = F;
      A.tracks[m] = F.T >= Math.round(cfg.win_s * cfg.fs) ? DSP.trackLink(F, cfg) : null;
      A.health[m] = DSP.linkHealth(S.links[m]);
      if (onProgress) onProgress(i + 1, S.macs.length);
    });
    return convertSession(S, A, name, profiles);
  }

  // ---------------------------------------------------------------- live streams
  // A stream is one LiveSession with its own packet statistics: the receiver's, and the injection bench's. They are
  // kept apart because the bench's chairs can use the same node addresses as real nodes.
  const newStream = (profiles) => ({ sess: new DSP.LiveSession(profiles || {}), stats: new Map() });
  let rx = null;                               // the receiver's stream
  function liveStats(S, L, rec) {
    let st = S.stats.get(L.mac);
    if (!st) { st = { t: [], step: [], prevDb: null, n: 0, slots: DSP.validSlots(L.fwi) }; S.stats.set(L.mac, st); }
    const db = packetDb(rec.H, st.slots);
    st.t.push(rec.t); st.step.push(st.prevDb !== null && Math.abs(db - st.prevDb) > 1.5 ? 1 : 0);
    st.prevDb = db; st.n++;
    while (st.t.length && st.t[0] < rec.t - 10) { st.t.shift(); st.step.shift(); }
    return st;
  }
  function decorate(S, u) {
    const L = S.sess.links.get(u.mac), st = S.stats.get(u.mac);
    let cnt = 0, steps = 0;
    for (let i = st.t.length - 1; i >= 0 && st.t[i] > u.t - 5; i--) { if (st.t[i] <= u.t) { cnt++; steps += st.step[i]; } }
    return Object.assign({}, u, {
      bpm: Number.isFinite(u.bpm) ? u.bpm : null, raw: Number.isFinite(u.raw) ? u.raw : null,
      pause: Number.isFinite(u.pause) ? u.pause : null, snr: Number.isFinite(u.snr) ? u.snr : null,
      wave: u.wave.map((x) => rnd(x, 3)), rate: rnd(cnt / 5, 2), steps: cnt ? rnd((100 * steps) / cnt, 1) : null,
      lossPct: rnd((100 * L.lost) / Math.max(L.lost + st.n, 1), 2), channel: L.channel, nsc: st.slots.length,
      rssi: rnd(u.rssi, 1), activity: rnd(u.activity, 3),
    });
  }
  /** One packet through a stream: returns the decorated update when it completes a 2 s hop. */
  function feed(S, r) {
    const u = S.sess.push(r);
    const L = S.sess.links.get(r.mac);
    if (L && L.recs.length) liveStats(S, L, L.recs[L.recs.length - 1]);
    return u ? decorate(S, u) : null;
  }

  // ---------------------------------------------------------------- injection bench (hinigram_inject.js)
  // Streams a recording's packets in real time (or faster), adds each chair's known breathing to them and runs them
  // through the same LiveSession as the receiver. With the receiver as the source, the breathing is added to the live
  // packets of the chairs it is switched on for, before the pipeline sees them.
  const INJ = G.HinigramInject;
  const TS0 = 100000000;                      // the bench's receiver clock: TS0 + stream time in microseconds
  const REC_CAP = 60e6;                        // keep at most about 60 MB of injected lines for the CSV download
  let bench = null;                            // {S, player, inj: Map mac -> ChairInjector, U, speed, running, timer, ...}
  let starting = null;                         // a bench start unpacking its packets: {cancel, queue of chair changes}
  let rxEpoch;                                 // the page's number for the current receiver session
  const rxInj = new Map();                     // receiver mode: mac -> ChairInjector
  const rec = { on: false, lines: [], bytes: 0, full: false };

  function recordLine(line) {
    if (!rec.on || rec.full) return;
    rec.lines.push(line); rec.bytes += line.length + 1;
    if (rec.bytes > REC_CAP) { rec.full = true; G.postMessage({ type: 'inject-recfull' }); }
  }
  function takeTruth(map) {
    const out = {};
    for (const [mac, ci] of map) { const t = ci.br.takeTruth(); if (t.t.length) out[mac] = t; }
    return out;
  }
  async function benchStart(m) {
    benchStop();
    if (starting) starting.cancel = true;      // a newer start replaces one still unpacking
    const st = starting = { cancel: false, queue: [] };
    let src;
    try {
      if (m.bg.kind === 'sample') src = await INJ.unpackSample(m.bg.b64);
      else src = INJ.recordsFromText(m.bg.text, DSP.parseLine);
    } finally { if (starting === st) starting = null; }
    if (st.cancel) return;                     // stopped, or replaced, while unpacking
    benchStop();
    if (!src.recs.length) throw new Error('no CSI_DATA lines');
    const chairs = m.chairs.map((c, i) => Object.assign({}, c, { src: src.macs[(c.srcIndex !== undefined ? c.srcIndex : i) % src.macs.length] }));
    const player = new INJ.Player(src, chairs.map((c, i) => ({ mac: c.mac, src: c.src, offset: c.offset, offsetFrac: c.offsetFrac, seqStart: 1 + 37 * i })), m.range || null);
    const inj = new Map();
    chairs.forEach((c, i) => inj.set(c.mac, new INJ.ChairInjector((m.seed || 1) * 100 + i, c.params)));
    const S = newStream(Object.fromEntries(chairs.map((c) => [c.mac, c.profile])));
    S.sess.t0us = TS0;                        // every chair on one clock that starts at stream time 0
    rec.on = !!m.record; rec.lines = []; rec.bytes = 0; rec.full = false;
    // every message of this run carries its number, so the page can drop a previous run's messages still in the queue
    bench = { S, player, inj, U: 0, speed: m.speed || 1, running: true, wall: performance.now(), busy: 0, span: 1, hostT0: m.hostT0 || Date.now() / 1000, run: m.run };
    G.postMessage({ type: 'inject-ready', run: m.run, D: player.D, a: player.a, links: src.macs, file: src.file || m.bg.name || '', chairs: player.chairs.map((c) => ({ mac: c.mac, src: c.src, offset: c.offset })) });
    st.queue.forEach(chairMessage);            // changes made while it was starting, before any packet is streamed
    pump(m.preroll || 0);
    bench.timer = setInterval(() => pump(0), 100);
  }
  function benchStop() {
    if (bench && bench.timer) clearInterval(bench.timer);
    bench = null;
  }
  /** Advance the stream to the wall clock times the speed: at most 1.5 s of stream per call, so the page stays
   *  responsive; a computer that cannot keep up runs the stream slower and reports its load. */
  function pump(extra) {
    const B = bench;
    if (!B) return;
    const now = performance.now(), dtWall = (now - B.wall) / 1000;
    B.wall = now;
    const want = B.running ? dtWall * B.speed : 0;
    const target = B.U + Math.min(want, 1.5 * Math.max(1, B.speed)) + (extra || 0);
    const ups = [];
    const t0 = performance.now();
    for (const p of B.player.until(target)) {
      const r = p.src, ci = B.inj.get(p.chair.mac);
      const o = ci.apply(r.raw, p.u, r.fwi, r.rssi);
      const pk = { t_host: B.hostT0 + p.u, seq: p.seq, mac: p.chair.mac, rssi: o.rssi, noise_floor: r.noise_floor, channel: r.channel,
        ts_us: (TS0 + Math.round(p.u * 1e6)) % INJ.TS_WRAP, sig_len: r.sig_len, rx_state: r.rx_state, len: 128, fwi: r.fwi, raw: o.raw };
      if (rec.on) recordLine(INJ.formatLine(pk.t_host, pk));
      const u = feed(B.S, pk);
      if (u) ups.push(u);
    }
    B.U = target;
    // share of wall time spent computing over the last few seconds; near 1 the computer cannot keep up
    B.busy = 0.8 * B.busy + 0.2 * (performance.now() - t0); B.span = 0.8 * B.span + 0.2 * Math.max(1, dtWall * 1000);
    if (ups.length) G.postMessage({ type: 'live', src: 'bench', run: B.run, updates: ups, packets: B.S.sess.packets });
    G.postMessage({ type: 'inject-tick', src: 'bench', run: B.run, t: B.U, running: B.running, speed: B.speed, load: Math.min(2, B.busy / B.span), truth: takeTruth(B.inj),
      rec: { on: rec.on, bytes: rec.bytes, full: rec.full, lines: rec.lines.length } });
  }
  /** Receiver mode: a live packet's time on the receiver session's own clock (the clock its updates use), worked out
   *  before the packet is pushed so the breathing can be added first. */
  function rxTime(r) {
    const s = rx.sess, L = s.links.get(r.mac);
    let tsU = r.ts_us;
    if (L) { tsU += L.tsAdd; if (L.tsPrev !== null && r.ts_us - L.tsPrev < -INJ.TS_WRAP / 2) tsU += INJ.TS_WRAP; }
    return s.t0us === null ? 0 : (tsU - s.t0us) / 1e6;
  }
  function chairFor(mac) { return bench ? bench.inj.get(mac) : rxInj.get(mac); }
  /** Stream time now: the bench's, or the newest packet's time on the receiver session's clock. */
  function nowT() {
    if (bench) return bench.U;
    let t = null;
    if (rx) for (const L of rx.sess.links.values()) if (L.recs.length) t = Math.max(t === null ? -Infinity : t, L.recs[L.recs.length - 1].t);
    return t;
  }

  /** One change to the bench or a chair: run or pause, speed, a chair's settings, simulated movement. */
  function chairMessage(m) {
    if (m.type === 'inject-run') {
      if (bench) { bench.running = !!m.running; bench.wall = performance.now(); }
    } else if (m.type === 'inject-speed') {
      if (bench) bench.speed = Math.max(0.25, Math.min(8, +m.speed || 1));
    } else if (m.type === 'inject-set') {
      // change one chair: bpm, depth, mode ('breathing' | 'hold' | 'empty'), on, script, profile
      const p = m.params || {};
      let ci = chairFor(m.mac);
      if (!ci && !bench && p.on) { ci = new INJ.ChairInjector(500 + rxInj.size, p); rxInj.set(m.mac, ci); }
      else if (ci) ci.set(p);
      if (p.profile) { if (bench) bench.S.sess.setProfile(m.mac, p.profile); else if (rx) rx.sess.setProfile(m.mac, p.profile); }
      G.postMessage({ type: 'inject-event', run: bench ? bench.run : undefined, mac: m.mac, t: nowT(), params: p, tag: m.tag || null });
    } else if (m.type === 'inject-move') {
      const ci = chairFor(m.mac);
      const t = nowT();
      if (ci && t !== null) ci.move(t, m.dur || 6);
      G.postMessage({ type: 'inject-event', run: bench ? bench.run : undefined, mac: m.mac, t, move: m.dur || 6, tag: m.tag || null });
    }
  }

  G.onmessage = async function (ev) {
    const m = ev.data || {};
    try {
      if (m.type === 'analyze') {
        const data = analyzeText(m.text, m.name, m.profiles, (done, total) => G.postMessage({ type: 'progress', done, total }));
        G.postMessage({ type: 'result', data });
      } else if (m.type === 'live-start') {
        rx = newStream(m.profiles);
        rxInj.clear();
        rxEpoch = m.epoch;
      } else if (m.type === 'live-profile') {
        if (rx) rx.sess.setProfile(m.mac, m.profile);
      } else if (m.type === 'live-lines') {
        if (!rx) rx = newStream({});
        const ups = [], heard = [];
        let tLast = null;
        for (const ln of m.lines) {
          let r = DSP.parseLine(ln);
          if (!r || r.len !== 128) { rx.sess.bad++; continue; }
          const fresh = !rx.sess.links.has(r.mac);
          if (rxInj.size || rec.on) {
            const t = rxTime(r), ci = rxInj.get(r.mac);
            tLast = t;
            if (ci) { const o = ci.apply(r.raw, t, r.fwi, r.rssi); r = Object.assign({}, r, { raw: o.raw, rssi: o.rssi }); recordLine(INJ.replaceCsi(ln, o.raw)); }
            else recordLine(ln);
          }
          const u = feed(rx, r);
          if (u) ups.push(u);
          if (fresh) { const L = rx.sess.links.get(r.mac); heard.push({ mac: r.mac, t: L && L.recs.length ? L.recs[L.recs.length - 1].t : 0 }); }
        }
        // a node's first packet: the bench can start its scenario now, not 30 s later at the node's first reading
        if (heard.length) G.postMessage({ type: 'inject-heard', epoch: rxEpoch, nodes: heard });
        if (ups.length) G.postMessage({ type: 'live', src: 'receiver', epoch: rxEpoch, updates: ups, packets: rx.sess.packets });
        if (rxInj.size) G.postMessage({ type: 'inject-tick', src: 'receiver', epoch: rxEpoch, t: tLast, truth: takeTruth(rxInj), rec: { on: rec.on, bytes: rec.bytes, full: rec.full, lines: rec.lines.length } });
      } else if (m.type === 'inject-start') {
        await benchStart(m);
      } else if (m.type === 'inject-stop') {
        if (starting) starting.cancel = true;
        benchStop();
      } else if (/^inject-(set|move|run|speed)$/.test(m.type)) {
        if (starting) starting.queue.push(m); else chairMessage(m);
      } else if (m.type === 'inject-record') {
        rec.on = !!m.on;
        if (m.clear) { rec.lines = []; rec.bytes = 0; rec.full = false; }
      } else if (m.type === 'inject-export') {
        // the first line marks the file as test data; the pipelines read only CSI_DATA lines
        G.postMessage({ type: 'inject-csv', text: (m.marker ? m.marker + '\n' : '') + rec.lines.join('\n') + (rec.lines.length ? '\n' : ''), lines: rec.lines.length });
      }
    } catch (e) {
      G.postMessage({ type: 'error', message: String((e && e.message) || e), during: m.type });
    }
  };
  G.HinigramWorker = { analyzeText, convertSession, series2hz };
})(typeof self !== 'undefined' ? self : this);
