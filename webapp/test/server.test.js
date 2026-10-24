'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { createServer } = require('../src/server');
const { Recorder } = require('../src/recorder');
const { candidates } = require('../src/receiver');
const { simulateLines } = require('../src/simulate');

/** A source the test drives by hand, with the events every real source emits. */
class FakeSource extends EventEmitter {
  constructor() {
    super();
    this.kind = 'demo';
  }
  start() {
    this.emit('status', { state: 'connected', path: 'simulated', message: 'fake' });
    return this;
  }
  async stop() {}
}

async function withServer(fn) {
  const source = new FakeSource();
  const server = createServer({ source, recorder: new Recorder({ dir: fs.mkdtempSync(path.join(os.tmpdir(), 'hinigram-srv-')) }) });
  source.start();
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    await fn(base, source);
  } finally {
    await server.shutdown();
  }
}

test('the API serves state built from the lines the source sends, junk included', async () => {
  await withServer(async (base, source) => {
    const t0 = Date.now() / 1000;
    source.emit('line', 'type,id,mac,rssi', t0); // csi_rx's header
    source.emit('line', '# dropped=4', t0);
    for (const [t, line] of simulateLines({ seconds: 3, seats: [{ id: 2, bpm: 15 }] })) source.emit('line', `ÿ\u0013${line}`, t0 + t);
    const s = await (await fetch(`${base}/api/state`)).json();
    assert.equal(s.receiver.state, 'connected');
    assert.equal(s.receiver.source, 'demo');
    assert.equal(s.stream.dropped, 4);
    assert.equal(s.sensors.length, 1);
    assert.equal(s.sensors[0].label, 'TX2');
    assert.equal(s.stream.unreadable, 0);
  });
});

test('the page and its assets are served; anything else is not', async () => {
  await withServer(async (base) => {
    const page = await fetch(`${base}/`);
    assert.equal(page.status, 200);
    assert.match(await page.text(), /<title>Hinigram live<\/title>/);
    assert.equal((await fetch(`${base}/app.js`)).headers.get('content-type'), 'text/javascript; charset=utf-8');
    assert.equal((await fetch(`${base}/fonts/AtkinsonHyperlegibleNext.ttf`)).status, 200);
    assert.equal((await fetch(`${base}/src/server.js`)).status, 404);
    assert.equal((await fetch(`${base}/recordings/..%2Fpackage.json`)).status, 404);
  });
});

test('recording starts and stops through the API, and a bad profile is refused', async () => {
  await withServer(async (base) => {
    const on = await (await fetch(`${base}/api/record/start`, { method: 'POST' })).json();
    assert.equal(on.on, true);
    assert.match(on.name, /^hinigram_sim_/);
    const off = await (await fetch(`${base}/api/record/stop`, { method: 'POST' })).json();
    assert.equal(off.on, false);
    const bad = await fetch(`${base}/api/profile`, { method: 'POST', body: JSON.stringify({ mac: '1a:00:00:00:00:01', profile: 'giant' }) });
    assert.equal(bad.status, 400);
  });
});

test('receiver search tries ESP32 USB-serial chips only, the last good port first', () => {
  const ports = [
    { path: 'COM3', vendorId: undefined },
    { path: 'COM8', vendorId: '1A86' },
    { path: 'COM5', vendorId: '10C4' },
  ];
  assert.deepEqual(candidates(ports, null), ['COM8', 'COM5']);
  assert.deepEqual(candidates(ports, 'COM5'), ['COM5', 'COM8']);
});
