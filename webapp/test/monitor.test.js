'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { Monitor, extendTrace, guidance, txNumber } = require('../src/monitor');
const { simulateLines } = require('../src/simulate');

/** Runs simulated seconds through a monitor; returns it and a snapshot taken at every pipeline update. */
function run(seconds, seats) {
  const m = new Monitor();
  const snaps = [];
  const t0 = 1_700_000_000;
  for (const [t, line] of simulateLines({ seconds, seats })) {
    if (m.ingest(line, t0 + t)) snaps.push(m.snapshot({ state: 'connected' }, { on: false }, t0 + t));
  }
  return { m, snaps, last: m.snapshot({ state: 'connected' }, { on: false }, t0 + seconds) };
}

const sensor = (snap, tx) => snap.sensors.find((s) => s.tx === tx);

test('the vendored pipeline reads the simulated seats: two rates and an empty chair', () => {
  const { last } = run(75);
  assert.equal(last.sensors.length, 3);
  const [s1, s2, s3] = [1, 2, 3].map((tx) => sensor(last, tx));
  assert.ok(s1.reading.reliable && Math.abs(s1.reading.bpm - 15) <= 1, `TX1 read ${s1.reading.bpm}`);
  assert.ok(s2.reading.reliable && Math.abs(s2.reading.bpm - 18) <= 1, `TX2 read ${s2.reading.bpm}`);
  assert.equal(s3.reading.reliable, false);
  assert.equal(s3.reading.status, 'no_reading');
  assert.equal(s1.guidance.level, 'good');
  assert.equal(s3.guidance.level, 'bad');
  assert.ok(s1.packetsPerS > 25 && s1.packetsPerS < 35);
});

test('a breath-hold on TX2 raises the pause alert and then resumes', () => {
  const { snaps } = run(115);
  const keys = snaps.map((s) => sensor(s, 2)).filter((s) => s && s.reading).map((s) => s.reading.key);
  assert.ok(keys.includes('pause'), `TX2 keys: ${[...new Set(keys)].join(', ')}`);
  assert.ok(keys.indexOf('resumed') > keys.indexOf('pause'));
});

test('the shown trace keeps its history: earlier samples never change after an update', () => {
  const { snaps } = run(80, [{ id: 1, bpm: 15 }]);
  let trimmed = false;
  for (let i = 1; i < snaps.length; i++) {
    const a = snaps[i - 1].sensors[0].trace, b = snaps[i].sensors[0].trace;
    // past 60 s the oldest samples drop off the front, so the old history sits `drop` places further left
    const drop = [...Array(41).keys()].find((d) => JSON.stringify(b.slice(0, a.length - d)) === JSON.stringify(a.slice(d)));
    assert.notEqual(drop, undefined, `update ${i} changed the history`);
    if (drop > 0) trimmed = true;
  }
  assert.ok(trimmed, 'the run should pass the 60 s mark');
});

test('a flipped window is turned back to match the shown trace, and joined without a step', () => {
  const w = Array.from({ length: 300 }, (_, i) => Math.sin(i / 6));
  const shown = extendTrace([], w.slice(), 300);
  const flipped = w.slice(20).concat(Array.from({ length: 20 }, (_, i) => Math.sin((300 + i) / 6))).map((x) => -x);
  extendTrace(shown, flipped, 20);
  assert.equal(shown.length, 320);
  for (let i = 300; i < 320; i++) assert.ok(Math.abs(shown[i] - Math.sin(i / 6)) < 0.25, `sample ${i}`);
});

test('the raw live signal is there within seconds, long before the 30 s analysis', () => {
  const { last } = run(4, [{ id: 1, bpm: 15 }]);
  const s = last.sensors[0];
  assert.equal(s.reading, null);
  assert.ok(s.live, 'no live signal after 4 s');
  assert.equal(s.live.values.length, 300);
  assert.ok(s.live.values.filter((v) => v !== null).length >= 30);
  assert.ok(Number.isInteger(s.live.subcarrier) && Math.abs(s.live.subcarrier) <= 26);
});

test('the last reliable rate is kept for a status the pipeline holds', () => {
  const { last } = run(75, [{ id: 1, bpm: 15 }]);
  const r = last.sensors[0].reading;
  assert.ok(r.lastReliable && Math.abs(r.lastReliable.bpm - 15) <= 1);
  assert.ok(r.lastReliable.ago >= 0);
});

test('guidance puts a silent transmitter first, then collecting, then placement', () => {
  const base = { tx: 1, firstPacket: 0, lastPacket: 100, rate: 30, rssi: -55, reading: null };
  assert.equal(guidance({ ...base, lastPacket: 90 }, 100).level, 'bad');
  assert.match(guidance(base, 110 - 7).title, /^Collecting/);
  assert.equal(guidance({ ...base, rate: 9 }, 100).level, 'warn');
  assert.equal(guidance({ ...base, reading: { reliable: false, quality: 0.2, motion: false } }, 100).title, 'No breathing pattern');
});

test('transmitter numbers come from the 1a:00:00:00:00:0N addresses', () => {
  assert.equal(txNumber('1a:00:00:00:00:03'), 3);
  assert.equal(txNumber('30:c6:f7:43:f5:0c'), null);
});

test('changing who sits in a seat starts that seat afresh', () => {
  const { m } = run(40, [{ id: 1, bpm: 15 }]);
  m.setProfile('1a:00:00:00:00:01', 'child_1_5y');
  const s = m.snapshot({}, { on: false }).sensors[0];
  assert.equal(s.profile, 'child_1_5y');
  assert.equal(s.reading, null);
  assert.throws(() => m.setProfile('1a:00:00:00:00:01', 'giant'), /unknown profile/);
});
