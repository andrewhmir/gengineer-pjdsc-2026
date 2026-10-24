'use strict';

// A simulated receiver: SIMULATED data in the exact CSI_DATA layout the team's csi_rx prints, so the whole
// app runs, and is tested, without hardware. Each link is a static path plus one reflection off the chest
// whose length moves a few millimetres with each breath, which every subcarrier sees differently, as on a
// real link.

const { EventEmitter } = require('node:events');

const C = 299792458;
const FC = 2.437e9; // Wi-Fi channel 6
const DF = 312500; // subcarrier spacing, HT20
const FS = 30; // packets per second per transmitter, as csi_tx sends
const TS_WRAP = 4294967296;

/** Seeded uniform random numbers (mulberry32). */
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gauss(r) {
  const u = Math.max(r(), 1e-12);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
}

// The three demo seats: steady breathing, breathing with an 18 s breath-hold every 2.5 minutes, an empty chair.
const DEMO_SEATS = [
  { id: 1, bpm: 15 },
  { id: 2, bpm: 18, holds: { every: 150, at: 75, length: 18 } },
  { id: 3, bpm: 0 },
];

/** One transmitter's link to the receiver. */
class Link {
  constructor(seat, seed) {
    const r = (this.r = rng(seed));
    this.seat = seat;
    this.mac = `1a:00:00:00:00:${String(seat.id).padStart(2, '0')}`;
    this.static = [];
    for (let s = 0; s < 64; s++) {
      const a = 18 + 8 * r(), ph = 2 * Math.PI * r();
      this.static.push([a * Math.cos(ph), a * Math.sin(ph)]);
    }
    this.d0 = 2.5 + r(); // metres along the chest reflection
    this.chest = seat.bpm > 0 ? 7 : 0;
    this.seq = Math.floor(r() * 5000);
    this.phase = 2 * Math.PI * r();
    this.rssi = -48 - Math.round(6 * r());
  }

  holding(t) {
    const h = this.seat.holds;
    if (!h) return false;
    const x = t % h.every;
    return x >= h.at && x < h.at + h.length;
  }

  /** The CSI_DATA line for a packet sent at session time t (s), stamped with the receiver clock tsUs. */
  line(t, dt, tsUs) {
    const r = this.r;
    if (this.seat.bpm > 0 && !this.holding(t)) this.phase += 2 * Math.PI * (this.seat.bpm / 60) * dt * (1 + 0.03 * Math.sin(t / 23));
    const d = this.d0 + 0.004 * Math.sin(this.phase);
    const g = 1 + 0.02 * gauss(r), th = 2 * Math.PI * r(); // per-packet gain and carrier phase, as the radio adds them
    const raw = new Array(128).fill(0);
    for (let s = 0; s < 64; s++) {
      const sc = s < 32 ? s : s - 64;
      if (!((s >= 1 && s <= 26) || (s >= 38 && s <= 63))) continue; // guard and DC slots carry nothing
      const ang = (-2 * Math.PI * (FC + sc * DF) * d) / C;
      const re0 = this.static[s][0] + this.chest * Math.cos(ang), im0 = this.static[s][1] + this.chest * Math.sin(ang);
      const re = g * (re0 * Math.cos(th) - im0 * Math.sin(th)) + 0.6 * gauss(r);
      const im = g * (re0 * Math.sin(th) + im0 * Math.cos(th)) + 0.6 * gauss(r);
      raw[2 * s] = Math.max(-127, Math.min(127, Math.round(im)));
      raw[2 * s + 1] = Math.max(-127, Math.min(127, Math.round(re)));
    }
    this.seq = (this.seq + 1) % 65536;
    const rssi = this.rssi + Math.round(gauss(r));
    const ts = Math.floor(tsUs % TS_WRAP);
    return `CSI_DATA,${this.seq},${this.mac},${rssi},11,1,0,0,1,1,0,0,0,0,-96,0,6,0,${ts},0,47,1,128,1,"[${raw.join(',')}]"`;
  }
}

/** All packets of `seconds` of simulated session, in arrival order, as [time (s), line] pairs. */
function simulateLines({ seconds = 60, seats = DEMO_SEATS, seed = 7 } = {}) {
  const links = seats.map((s, i) => new Link(s, seed * 101 + i));
  const jitter = rng(seed);
  const out = [];
  links.forEach((L, i) => {
    let t = i / (FS * links.length);
    while (t < seconds) {
      const dt = 1 / FS + 0.002 * (jitter() - 0.5);
      t += dt;
      out.push([t, L, dt]);
    }
  });
  out.sort((a, b) => a[0] - b[0]);
  return out.map(([t, L, dt]) => [t, L.line(t, dt, 1e8 + t * 1e6)]);
}

/** A receiver that streams simulated packets in real time, with the same events as SerialReceiver. */
class DemoReceiver extends EventEmitter {
  constructor({ seats = DEMO_SEATS, seed = Date.now() % 100000 } = {}) {
    super();
    this.links = seats.map((s, i) => new Link(s, seed * 101 + i));
    this.kind = 'demo';
  }

  start() {
    this.t0 = Date.now() / 1000;
    this.next = this.links.map((_, i) => i / (FS * this.links.length));
    this.state = { state: 'connected', path: 'simulated', baud: null, message: 'Demo mode: simulated data, no receiver attached' };
    setImmediate(() => this.emit('status', this.state));
    this.timer = setInterval(() => this.tick(), 50);
    return this;
  }

  tick() {
    const now = Date.now() / 1000 - this.t0;
    this.links.forEach((L, i) => {
      while (this.next[i] <= now) {
        const dt = 1 / FS;
        this.next[i] += dt;
        this.emit('line', L.line(this.next[i], dt, 1e8 + this.next[i] * 1e6), this.t0 + this.next[i]);
      }
    });
  }

  async stop() {
    clearInterval(this.timer);
  }
}

module.exports = { DemoReceiver, simulateLines, DEMO_SEATS };
