'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { ModelSidecar } = require('../src/model');
const { Monitor } = require('../src/monitor');
const { connect } = require('../src/server');
const { Recorder } = require('../src/recorder');
const { simulateLines } = require('../src/simulate');
const { EventEmitter } = require('node:events');

// Stands in for model/resonet_sidecar.py with the same protocol, so the test needs neither Python nor jax:
// "ready", then one estimate per 30 CSI_DATA lines of a transmitter, and the control lines echoed.
const FAKE = `
const rl = require('node:readline').createInterface({ input: process.stdin });
const seen = {};
console.log(JSON.stringify({ type: 'ready', variant: 'lin_sync-e80', n_models: 6 }));
rl.on('line', (line) => {
  if (line.startsWith('#')) return console.log(JSON.stringify({ type: 'control', line }));
  const mac = line.split(',')[2];
  seen[mac] = (seen[mac] || 0) + 1;
  if (seen[mac] % 30 === 0) console.log(JSON.stringify({ type: 'estimate', mac, t: seen[mac] / 30, rate: 15.2, n_shown: 5, n_models: 6, p_present: 0.98, models: [] }));
});
`;

function fakeSidecar() {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'hinigram-model-')), 'fake.js');
  fs.writeFileSync(file, FAKE);
  return new ModelSidecar({ command: [process.execPath, [file]] });
}

const once = (em, ev, pred = () => true) => new Promise((resolve) => {
  const f = (x) => { if (pred(x)) { em.off(ev, f); resolve(x); } };
  em.on(ev, f);
});

test('estimates from the helper reach the right transmitter, beside its reading and not in it', async () => {
  const model = fakeSidecar();
  const monitor = new Monitor();
  const source = new EventEmitter();
  connect(source, monitor, new Recorder({ dir: fs.mkdtempSync(path.join(os.tmpdir(), 'hinigram-rec-')) }), model);
  const ready = once(model, 'state', (s) => s.state === 'ready');
  model.start();
  await ready;
  assert.equal(monitor.modelState.state, 'ready');
  const got = once(model, 'estimate');
  const t0 = Date.now() / 1000;
  for (const [t, line] of simulateLines({ seconds: 2, seats: [{ id: 2, bpm: 15 }] })) source.emit('line', line, t0 + t);
  const est = await got;
  assert.equal(est.mac, '1a:00:00:00:00:02');
  const s = monitor.snapshot({}, { on: false }).sensors[0];
  assert.deepEqual({ rate: s.model.rate, nShown: s.model.nShown, nModels: s.model.nModels }, { rate: 15.2, nShown: 5, nModels: 6 });
  assert.equal(s.reading, null, 'the model must not create a pipeline reading');
  await model.stop();
});

test('a change of who sits in a seat is passed on to the helper', async () => {
  const model = fakeSidecar();
  const ready = once(model, 'state', (s) => s.state === 'ready');
  model.start();
  await ready;
  const echoed = new Promise((resolve) => model.child.stdout.on('data', (c) => String(c).includes('#profile') && resolve(String(c))));
  model.setProfile('1a:00:00:00:00:01', 'child_1_5y');
  assert.match(await echoed, /#profile 1a:00:00:00:00:01 child_1_5y/);
  await model.stop();
});

test('without the bundle the model is unavailable, and says where it looked', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hinigram-nobundle-'));
  const model = new ModelSidecar({ bundle: dir }).start();
  assert.equal(model.state.state, 'unavailable');
  assert.ok(model.state.message.includes(dir));
});
