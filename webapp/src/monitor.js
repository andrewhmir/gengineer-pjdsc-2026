'use strict';

// Runs every packet through the Hinigram v1.3.2 pipeline (vendor/hinigram_dsp.js, unchanged) and keeps what
// the console shows for each transmitter: link health, the latest reading, a steady breathing trace and a
// placement hint.

const DSP = require('../vendor/hinigram_dsp.js');

const FS = 10; // the pipeline's resampled rate; its trace is the last 30 s at this rate
const TRACE_S = 60;
const QUALITY_S = 120;
const TREND_MAX = 1800; // one reading per 2 s hop: an hour
const RATE_S = 5;
const STALE_S = 3;
const LIVE_S = 30; // the raw live signal, shown from the first packet, before the pipeline has a window
const LIVE_SMOOTH = 10; // bins (1 s) of moving average against per-packet noise
const LIVE_PICK_S = 10; // the subcarrier is chosen on the last 10 s, and kept unless another moves twice as much

const round = (x, d = 2) => (Number.isFinite(x) ? Math.round(x * 10 ** d) / 10 ** d : null);

function median(a) {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  return s[s.length >> 1];
}

function packetDb(H, slots) {
  let ss = 0;
  for (const s of slots) ss += H.re[s] * H.re[s] + H.im[s] * H.im[s];
  return 20 * Math.log10(Math.sqrt(ss / slots.length) + 1e-9);
}

/** The transmitter number from its address: 1a:00:00:00:00:0N is TX N. */
function txNumber(mac) {
  const m = /^1a:00:00:00:00:([0-9a-f]{2})$/.exec(mac);
  return m ? parseInt(m[1], 16) : null;
}

/**
 * Appends the newest part of a pipeline trace to the shown trace. Each update re-analyses the last 30 s, so
 * its trace can come back flipped or reshaped; only the samples after the previous update are added, turned
 * to match the overlap with what is already shown and joined to it without a step. History never changes.
 */
function extendTrace(shown, w, nNew) {
  if (!shown.length || nNew >= w.length) {
    if (shown.length) shown.push(null); // a gap: the line breaks here
    shown.push(...w);
    return shown;
  }
  const overlap = w.length - nNew;
  const tail = shown.slice(-overlap);
  let dot = 0;
  for (let i = 0; i < overlap; i++) if (tail[i] !== null) dot += tail[i] * w[i];
  const sign = dot < 0 ? -1 : 1;
  const last = shown[shown.length - 1];
  const step = last === null ? 0 : last - sign * w[overlap - 1];
  for (let i = 0; i < nNew; i++) shown.push(sign * w[overlap + i] + step * (1 - (i + 1) / nNew));
  return shown;
}

/** Adds one packet's amplitudes, divided by their mean so the radio's gain changes cancel, to 0.1 s bins. */
function addLiveSample(live, t, H, slots) {
  const amp = slots.map((k) => Math.hypot(H.re[k], H.im[k]));
  const mean = amp.reduce((a, b) => a + b, 0) / amp.length;
  if (!(mean > 0)) return;
  const bin = Math.floor(t * FS);
  let last = live.bins[live.bins.length - 1];
  if (!last || last.bin !== bin) {
    last = { bin, sum: new Float64Array(slots.length), n: 0 };
    live.bins.push(last);
  }
  for (let i = 0; i < amp.length; i++) last.sum[i] += amp[i] / mean;
  last.n++;
  while (live.bins.length && live.bins[0].bin < bin - LIVE_S * FS) live.bins.shift();
  live.slots = slots;
}

/**
 * The raw live signal for the last 30 s: the subcarrier that moves most, smoothed over 1 s and scaled to its own
 * spread. It shows movement and, on a good link, breathing from the first second. It is not the analysis.
 */
function liveSignal(live, now) {
  if (!live.slots || live.bins.length < LIVE_SMOOTH * 2) return null;
  const end = Math.floor(now * FS), start = end - LIVE_S * FS + 1, nSc = live.slots.length;
  const rows = new Array(LIVE_S * FS).fill(null);
  for (const b of live.bins) if (b.bin >= start && b.bin <= end) rows[b.bin - start] = Array.from(b.sum, (x) => x / b.n);
  const smooth = (c) => rows.map((_, i) => {
    let s = 0, n = 0;
    for (let j = Math.max(0, i - LIVE_SMOOTH + 1); j <= i; j++) if (rows[j]) { s += rows[j][c]; n++; }
    return rows[i] && n ? s / n : null;
  });
  const spread = (xs) => {
    const v = xs.filter((x) => x !== null);
    if (v.length < 3) return { sd: 0, mean: 0 };
    const mean = v.reduce((a, b) => a + b, 0) / v.length;
    return { mean, sd: Math.sqrt(v.reduce((a, b) => a + (b - mean) ** 2, 0) / v.length) };
  };
  const recentSd = (c) => spread(smooth(c).slice(-LIVE_PICK_S * FS)).sd;
  let best = 0, bestSd = -1;
  for (let c = 0; c < nSc; c++) {
    const sd = recentSd(c);
    if (sd > bestSd) { best = c; bestSd = sd; }
  }
  if (live.pick === null || live.pick >= nSc || recentSd(live.pick) * 2 < bestSd) live.pick = best;
  const series = smooth(live.pick), { mean, sd } = spread(series);
  const k = live.slots[live.pick];
  return { values: series.map((x) => (x === null || !(sd > 0) ? null : round((x - mean) / sd, 3))), fs: FS, subcarrier: k < 32 ? k : k - 64 };
}

/** The one thing to do next for a transmitter, in the order a person setting up would need it. */
function guidance(s, now) {
  const tx = s.tx ? `TX${s.tx}` : 'this transmitter';
  const ago = now - s.lastPacket;
  if (ago > STALE_S) return { level: 'bad', title: `No packets from ${tx} for ${Math.round(ago)} s`, detail: `Check that ${tx} has power, and that it is within a few metres of the receiver.` };
  if (s.rate < 15) return { level: 'warn', title: `Packets are getting lost (${Math.round(s.rate)} a second of 30)`, detail: 'Move the receiver closer, or clear people and furniture out of the line between them.' };
  if (s.rssi !== null && s.rssi < -80) return { level: 'warn', title: `Weak signal (${s.rssi} dBm)`, detail: 'Move the receiver closer, or turn the node so its antenna end points at the receiver.' };
  const r = s.reading;
  if (!r) {
    const got = Math.min(30, Math.floor(now - s.firstPacket));
    return { level: 'info', title: `Collecting: ${got} of 30 s`, detail: 'The first reading comes after 30 seconds. Sit still and breathe normally.' };
  }
  if (r.motion || r.status === 'moving') return { level: 'warn', title: 'Movement', detail: 'Sit still with hands in the lap. Readings come back after about 16 to 30 seconds without movement.' };
  if (r.reliable) return { level: 'good', title: 'Breathing pattern found', detail: 'This placement works. Keep the node and the receiver where they are.' };
  if (r.quality >= 0.6) return { level: 'ok', title: 'A pattern is forming', detail: 'Keep still. A reading needs the pattern to stay steady for a few more seconds.' };
  return {
    level: 'bad', title: 'No breathing pattern',
    detail: 'The person must sit between the node and the receiver: node on the back of the chair at chest height, receiver 2 to 3 m in front at chest height. Then try the node a few centimetres higher or lower.',
  };
}

class Monitor {
  constructor({ profiles = {} } = {}) {
    this.profiles = { ...profiles };
    this.modelState = { state: 'off', message: 'Model estimate is off' };
    this.reset();
  }

  /** The ResoNet helper's newest readings for a transmitter. Shown beside the reading; never part of it. */
  setModel(mac, est, t = Date.now() / 1000) {
    const s = this.sensors.get(mac);
    if (s) s.model = { rate: est.rate, nShown: est.n_shown, nModels: est.n_models, pPresent: est.p_present, at: t };
  }

  /** Starts afresh: new pipeline session, no history. Keeps each transmitter's age profile. */
  reset() {
    this.sess = new DSP.LiveSession({ ...this.profiles });
    this.sensors = new Map();
    this.counts = { lines: 0, csi: 0, bad: 0, other: 0, dropped: null };
    this.lineTimes = [];
    this.lineBytes = [];
    this.startedAt = Date.now() / 1000;
  }

  setProfile(mac, profile) {
    if (!DSP.PROFILES[profile]) throw new Error(`unknown profile ${profile}`);
    this.profiles[mac] = profile;
    this.sess.setProfile(mac, profile);
    const s = this.sensors.get(mac);
    if (s) Object.assign(s, { profile, reading: null, lastReliable: null, model: null, quality: [], trend: [] });
  }

  sensor(mac) {
    let s = this.sensors.get(mac);
    if (!s) {
      s = {
        mac, tx: txNumber(mac), profile: this.profiles[mac] || 'adult', firstPacket: null, lastPacket: null,
        count: 0, arrivals: [], rssis: [], steps: [], lostAt: [], prevDb: null, rate: 0, rssi: null,
        reading: null, lastReliable: null, model: null, trace: [], traceT: null, quality: [], trend: [],
        live: { bins: [], slots: null, pick: null },
      };
      this.sensors.set(mac, s);
    }
    return s;
  }

  /** One CSI_DATA record (text) that arrived at host time t (s). Returns the pipeline update, if any. */
  ingest(text, t) {
    this.counts.csi++;
    const rec = DSP.parseLine(text);
    if (!rec || rec.len !== 128) {
      this.counts.bad++;
      return null;
    }
    const s = this.sensor(rec.mac);
    if (s.firstPacket === null) s.firstPacket = t;
    s.lastPacket = t;
    s.count++;
    s.arrivals.push(t);
    s.rssis.push(rec.rssi);
    const u = this.sess.push(rec);
    const L = this.sess.links.get(rec.mac);
    s.lostAt.push(L ? L.lost : 0); // the pipeline's running count of sequence gaps, for the loss over the last 5 s
    if (L && L.recs.length) {
      const slots = DSP.validSlots(L.fwi);
      addLiveSample(s.live, t, L.recs[L.recs.length - 1].H, slots);
      const db = packetDb(L.recs[L.recs.length - 1].H, slots);
      s.steps.push(s.prevDb !== null && Math.abs(db - s.prevDb) > 1.5 ? 1 : 0);
      s.prevDb = db;
    }
    while (s.arrivals.length && s.arrivals[0] < t - RATE_S) {
      s.arrivals.shift();
      s.rssis.shift();
      s.steps.shift();
      s.lostAt.shift();
    }
    if (u) this.onUpdate(s, u);
    return u;
  }

  /** A raw line from the receiver: counted, and passed on when it carries a CSI_DATA record. */
  line(text, t) {
    this.counts.lines++;
    this.lineTimes.push(t);
    this.lineBytes.push(text.length + 1); // how full the serial link is sets how many transmitters one receiver carries
    while (this.lineTimes.length && this.lineTimes[0] < t - RATE_S) {
      this.lineTimes.shift();
      this.lineBytes.shift();
    }
    return text;
  }

  onUpdate(s, u) {
    const nNew = s.traceT === null ? u.wave.length : Math.max(1, Math.round((u.t - s.traceT) * FS));
    extendTrace(s.trace, u.wave, nNew);
    if (s.trace.length > TRACE_S * FS) s.trace.splice(0, s.trace.length - TRACE_S * FS);
    s.traceT = u.t;
    s.reading = {
      t: u.t, status: u.status, key: u.key, reason: u.reason, reliable: u.reliable,
      bpm: Number.isFinite(u.bpm) ? u.bpm : null, raw: Number.isFinite(u.raw) ? u.raw : null,
      quality: u.quality, snr: Number.isFinite(u.snr) ? u.snr : null, motion: u.motion,
      activity: Number.isFinite(u.activity) ? u.activity : null, pause: Number.isFinite(u.pause) ? u.pause : null,
    };
    // The pipeline keeps a rate-based status for a few seconds after a reading stops being reliable, so the
    // console needs the rate that status came from.
    if (s.reading.reliable && s.reading.bpm !== null) s.lastReliable = { bpm: s.reading.bpm, t: u.t };
    s.quality.push({ t: u.t, q: u.quality, reliable: u.reliable, motion: u.motion });
    while (s.quality.length && s.quality[0].t < u.t - QUALITY_S) s.quality.shift();
    s.trend.push({ t: u.t, bpm: s.reading.bpm, status: u.status });
    if (s.trend.length > TREND_MAX) s.trend.shift();
  }

  snapshot(receiver, recording, now = Date.now() / 1000) {
    // counted against now, not the last arrival: when lines stop, the rate must fall to 0
    const lineRate = this.lineTimes.filter((x) => x > now - RATE_S).length / RATE_S;
    const byteRate = this.lineBytes.reduce((a, b, i) => a + (this.lineTimes[i] > now - RATE_S ? b : 0), 0) / RATE_S;
    const sensors = [...this.sensors.values()].sort((a, b) => (a.tx || 99) - (b.tx || 99) || a.mac.localeCompare(b.mac)).map((s) => {
      s.rate = s.arrivals.filter((x) => x > now - RATE_S).length / RATE_S;
      s.rssi = median(s.rssis);
      const L = this.sess.links.get(s.mac);
      const lost = L ? L.lost : 0;
      const recentLost = s.lostAt.length ? s.lostAt[s.lostAt.length - 1] - s.lostAt[0] : 0;
      const r = s.reading;
      return {
        mac: s.mac, tx: s.tx, label: s.tx ? `TX${s.tx}` : s.mac, profile: s.profile,
        packetsPerS: round(s.rate, 1), rssi: s.rssi,
        lossPct: round((100 * recentLost) / Math.max(1, recentLost + s.lostAt.length), 1), // last 5 s
        lossSessionPct: round((100 * lost) / Math.max(1, lost + s.count), 1),
        gainStepsPct: s.steps.length ? round((100 * s.steps.reduce((a, b) => a + b, 0)) / s.steps.length, 1) : null,
        lastPacketAgo: round(now - s.lastPacket, 1), collectedS: round(now - s.firstPacket, 0),
        stale: now - s.lastPacket > STALE_S, // everything below is then old: shown as old, not as now
        reading: r && {
          ...r, t: round(r.t, 1), bpm: round(r.bpm, 1), raw: round(r.raw, 1), quality: round(r.quality, 2),
          snr: round(r.snr, 1), activity: round(r.activity, 2), pause: round(r.pause, 1),
          lastReliable: s.lastReliable ? { bpm: round(s.lastReliable.bpm, 1), ago: round(r.t - s.lastReliable.t, 0) } : null,
        },
        model: s.model && { rate: round(s.model.rate, 1), nShown: s.model.nShown, nModels: s.model.nModels, pPresent: round(s.model.pPresent, 2), ago: round(now - s.model.at, 0) },
        live: liveSignal(s.live, now),
        trace: s.trace.map((x) => (x === null ? null : round(x, 3))), traceFs: FS,
        quality: s.quality.map((x) => ({ t: round(x.t, 1), q: round(x.q, 2), reliable: x.reliable, motion: x.motion })),
        trend: s.trend.map((x) => ({ t: round(x.t, 1), bpm: round(x.bpm, 1), status: x.status })),
        guidance: guidance(s, now),
      };
    });
    return {
      now: round(now, 1), startedAt: round(this.startedAt, 1), receiver, recording, model: this.modelState,
      // dropped/logged: the receiver's own counts of lines it could not send and did send (bundle firmware)
      stream: { linesPerS: round(lineRate, 1), bytesPerS: Math.round(byteRate), lines: this.counts.lines, records: this.counts.csi, unreadable: this.counts.bad, dropped: this.counts.dropped, logged: this.counts.logged ?? null },
      profiles: Object.fromEntries(Object.entries(DSP.PROFILES).map(([k, v]) => [k, v.label])),
      sensors,
    };
  }
}

module.exports = { Monitor, extendTrace, guidance, txNumber };
