'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { BoardManager, parseBootLog, esptoolEvent, teamLabels, imageKey, readLibrary } = require('../src/boards');
const { createServer } = require('../src/server');
const { Recorder } = require('../src/recorder');

const C = (s) => `\x1b[0;32m${s}\x1b[0m`; // the colour codes ESP-IDF puts around each log line
const W = (s) => `\x1b[0;33m${s}\x1b[0m`;

// start-up logs as these boards printed them on 2026-10-24
const TX1_LOG = [
  'ets Jul 29 2019 12:21:46', 'rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)',
  C('I (390) app_init: Project name:     csi_tx1'), C('I (406) app_init: ESP-IDF:          v6.0'),
  'I (681) wifi:mode : sta (4c:c3:82:c4:59:b4)', C('I (692) csi_tx1: wifi_channel: 6, send_frequency: 30, mac: 1a:00:00:00:00:01'),
].join('\r\n');
const RX_LOG = [
  C('I (320) app_init: Project name:     csi_rx'), C('I (323) app_init: ESP-IDF:          v5.3.2-dirty'),
  'I (484) wifi:mode : sta (30:c6:f7:43:f5:0c)', 'type,id,mac,rssi,rate',
  'CSI_DATA,5861,1a:00:00:00:00:01,-54,11,1,0,0,1,1,0,0,0,0,-96,0,6,0,5839980,0,47,1,128,1,"[47,-16,2]"',
].join('\n');
const NODE_LOG = [
  'rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)', C('I (31) boot: ESP-IDF v5.3.2-dirty 2nd stage bootloader'),
  W('W (550) hinigram_node: node 1 sending 30 packets/s on channel 6 from 1a:00:00:00:00:01'),
].join('\n');
// what hinigram_universal_node prints, as its app_main.c writes it
const UNIVERSAL_LOG = [
  'rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)',
  W('W (548) hinigram_node: node 17 sending 30 packets/s on channel 6 from 1a:00:00:00:00:11'),
  W('W (549) hinigram_node: universal v1.0.0, chip d0:ef:76:56:e8:68, id stored, IDF v5.3.2-dirty'),
].join('\n');

const pickId = ({ project, role, id, set, version, chipMac, sendsAs }) => ({ project, role, id, set, version, chipMac, sendsAs });

test('a start-up log says which role a board runs, and its chip address', () => {
  assert.deepEqual(pickId(parseBootLog(TX1_LOG)), { project: 'csi_tx1', role: 'tx', id: 1, set: 'team', version: null, chipMac: '4c:c3:82:c4:59:b4', sendsAs: '1a:00:00:00:00:01' });
  const rx = parseBootLog(RX_LOG);
  assert.deepEqual([rx.role, rx.set, rx.chipMac, rx.csi], ['rx', 'team', '30:c6:f7:43:f5:0c', true]);
});

test('the universal node is known by its version line, with its ID, stored or not', () => {
  const u = parseBootLog(UNIVERSAL_LOG);
  assert.deepEqual(pickId(u), { project: 'hinigram_universal_node', role: 'tx', id: 17, set: 'universal', version: '1.0.0', chipMac: 'd0:ef:76:56:e8:68', sendsAs: '1a:00:00:00:00:11' });
  assert.equal(u.idStored, true);
  assert.equal(u.idf, 'v5.3.2-dirty');
  assert.equal(parseBootLog(UNIVERSAL_LOG.replace('id stored', 'id from the chip address')).idStored, false);
});

test("the bundle's firmware is told apart from the team's and the universal", () => {
  const n = parseBootLog(NODE_LOG);
  assert.deepEqual([n.role, n.id, n.set, n.project, n.idf], ['tx', 1, 'bundle', 'hinigram_node', 'v5.3.2-dirty']);
  const rx = parseBootLog('HINIGRAM_RX,receiver=1,chip=esp32,rev=3,idf=v5.3.2,channel=6,bandwidth=HT20,nodes=1-254,logged=0,dropped=0');
  assert.deepEqual([rx.role, rx.project], ['rx', 'hinigram_receiver']);
  assert.equal(parseBootLog('\x00\xff garbage').booted, false);
});

test("esptool's output becomes progress, and a board that needs BOOT is recognised", () => {
  assert.deepEqual(esptoolEvent('Connecting......'), { phase: 'connecting' });
  assert.deepEqual(esptoolEvent('Writing at 0x00034000... (45 %)'), { phase: 'writing', pct: 45 });
  assert.deepEqual(esptoolEvent('MAC: 30:c6:f7:43:f5:0c'), { flashedMac: '30:c6:f7:43:f5:0c' });
  assert.deepEqual(esptoolEvent('Hash of data verified.'), { phase: 'verified' });
  const boot = esptoolEvent('A fatal error occurred: Failed to connect to Espressif device: Wrong boot mode detected (0x13)! The chip needs to be in download mode.');
  assert.equal(boot.needBoot, true);
  assert.match(boot.error, /Wrong boot mode/);
  assert.equal(esptoolEvent('Stub running...'), null);
});

test('the receiver search knows a receiver by its banner, even with no transmitter on air', () => {
  const { RECEIVER_SIGN } = require('../src/receiver');
  assert.ok(RECEIVER_SIGN.test(RX_LOG.split('\n')[0]), 'csi_rx banner');
  assert.ok(RECEIVER_SIGN.test('HINIGRAM_RX,receiver=1,chip=esp32,channel=6'));
  assert.ok(![...TX1_LOG.split('\r\n'), ...UNIVERSAL_LOG.split('\n')].some((l) => RECEIVER_SIGN.test(l)), 'a transmitter is not a receiver');
});

test("the team's labels come from each csi_* README's MAC line", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hinigram-fw-'));
  const macs = { csi_rx: 'AA:BB:CC:00:00:0F', csi_tx1: 'AA:BB:CC:00:00:01', csi_tx2: 'AA:BB:CC:00:00:02' }; // csi_tx3 has none
  for (const p of ['csi_rx', 'csi_tx1', 'csi_tx2', 'csi_tx3']) {
    fs.mkdirSync(path.join(dir, p));
    if (macs[p]) fs.writeFileSync(path.join(dir, p, 'README.md'), `# ${p}\n- MAC:    ${macs[p]}\n`);
  }
  assert.deepEqual(teamLabels(dir), { 'aa:bb:cc:00:00:0f': 'RX', 'aa:bb:cc:00:00:01': 'TX1', 'aa:bb:cc:00:00:02': 'TX2' });
});

test('fixed firmware sets have one image per ID; the universal set one for any ID', () => {
  assert.equal(imageKey('team', 'tx', 2), 'tx2');
  assert.equal(imageKey('universal', 'tx', 40), 'tx');
  assert.equal(imageKey('bundle', 'rx', null), 'rx');
});

test('the next free ID skips every ID on USB and on air', () => {
  const m = new BoardManager({ firmwareDir: null });
  m.remember('COM5', parseBootLog(UNIVERSAL_LOG)); // ID 17
  m.remember('COM8', parseBootLog(RX_LOG));
  assert.equal(m.nextId([1, 2]), 3);
  assert.equal(m.nextId([...Array(16).keys()].map((i) => i + 1)), 18, '1 to 16 on air, 17 on USB');
});

test('every library version is kept, newest first, and an ID a fixed set lacks is refused', async () => {
  const lib = fs.mkdtempSync(path.join(os.tmpdir(), 'hinigram-lib-'));
  const entry = (set, version, builtAt, images) => ({ key: `${set}@${version}`, set, version, builtAt, idfVersion: 'v5.3.2', source: {}, images });
  fs.writeFileSync(path.join(lib, 'index.json'), JSON.stringify([
    entry('team', '2c9a02c', '2026-10-24T08:00:00Z', { rx: { file: 'a.bin' }, tx1: { file: 'b.bin' } }),
    entry('universal', '1.0.0+abc1234', '2026-10-24T09:00:00Z', { rx: { file: 'c.bin' }, tx: { file: 'd.bin' } }),
    entry('team', '1111111', '2026-10-23T08:00:00Z', { rx: { file: 'e.bin' } }),
  ]));
  assert.deepEqual(readLibrary(lib).map((e) => e.key), ['universal@1.0.0+abc1234', 'team@2c9a02c', 'team@1111111']);
  const m = new BoardManager({ firmwareDir: null, library: lib });
  await assert.rejects(m.flash('COM5', { role: 'tx', id: 7, version: 'team@2c9a02c' }), /transmitters 1, 2, 3 only/);
  await assert.rejects(m.flash('COM5', { role: 'tx', id: 300, version: 'universal@1.0.0+abc1234' }), /1 to 254/);
  await assert.rejects(m.flash('COM5', { role: 'rx', version: 'team@nope' }), /No firmware version/);
});

test('the Boards API touches only ports listed as ESP32 boards', async () => {
  const source = new EventEmitter();
  source.kind = 'demo';
  source.stop = async () => {};
  const calls = [];
  const boards = {
    job: null,
    list: async () => ({ boards: [{ path: 'COM5' }], versions: [], sets: {} }),
    identify: async (p) => { calls.push(['identify', p]); return { role: 'rx' }; },
    flash: async (p, opts) => { calls.push(['flash', p, opts]); return { port: p, phase: 'starting' }; },
    setId: async (p, id) => { calls.push(['setId', p, id]); return { id }; },
  };
  const server = createServer({ source, boards, recorder: new Recorder({ dir: fs.mkdtempSync(path.join(os.tmpdir(), 'hinigram-b-')) }) });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;
  const post = (p, body) => fetch(base + p, { method: 'POST', body: JSON.stringify(body) });
  try {
    assert.equal((await post('/api/boards/identify', { path: 'COM5' })).status, 200);
    assert.equal((await post('/api/boards/flash', { path: '\\\\.\\PHYSICALDRIVE0', role: 'rx' })).status, 400);
    assert.equal((await post('/api/boards/flash', { path: 'COM5', role: 'tx', id: 9, version: 'universal@1.0.0' })).status, 200);
    assert.equal((await post('/api/boards/set-id', { path: 'COM5', id: 12 })).status, 200);
    assert.deepEqual(calls, [['identify', 'COM5'], ['flash', 'COM5', { role: 'tx', id: 9, version: 'universal@1.0.0' }], ['setId', 'COM5', 12]]);
  } finally {
    await server.shutdown();
  }
});

test("the bundle receiver's own tally is read from its status line", () => {
  const { droppedOf, loggedOf } = require('../src/lines');
  const line = 'HINIGRAM_RX,receiver=1,chip=esp32,channel=6,nodes=1-3,logged=5321,dropped=17';
  assert.equal(loggedOf(line), 5321);
  assert.equal(droppedOf(line), 17);
});
