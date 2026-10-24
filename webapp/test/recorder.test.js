'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const DSP = require('../vendor/hinigram_dsp.js');
const { Recorder } = require('../src/recorder');
const { readRecording } = require('../src/replay');
const { simulateLines } = require('../src/simulate');

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'hinigram-rec-'));
const settle = (rec) => new Promise((resolve) => rec.out.on('finish', resolve));

test("recordings use log_serial.py's format, which the pipeline's parser reads with the host time", async () => {
  const rec = new Recorder({ dir: tmp() });
  rec.start('sim');
  const lines = simulateLines({ seconds: 2, seats: [{ id: 1, bpm: 15 }] });
  lines.forEach(([t, line]) => rec.write(1_700_000_000 + t, line));
  const done = settle(rec);
  const state = rec.stop();
  await done;
  assert.match(state.saved.name, /^hinigram_sim_\d{8}_\d{6}\.csv$/);
  const text = fs.readFileSync(path.join(rec.dir, state.saved.name), 'latin1').trimEnd().split('\n');
  assert.equal(text.length, lines.length);
  assert.match(text[0], /^\d{10}\.\d{6},CSI_DATA,/);
  const r = DSP.parseLine(text[0]);
  assert.ok(r && r.len === 128 && Math.abs(r.t_host - (1_700_000_000 + lines[0][0])) < 1e-5);
});

test('a recording replays in its own timing, from the host timestamps', async () => {
  const rec = new Recorder({ dir: tmp() });
  rec.start('sim');
  simulateLines({ seconds: 3, seats: [{ id: 1, bpm: 15 }] }).forEach(([t, line]) => rec.write(1_700_000_000 + t, line));
  const done = settle(rec);
  const { saved } = rec.stop();
  await done;
  const back = readRecording(path.join(rec.dir, saved.name));
  assert.equal(back.length, saved.lines);
  assert.equal(back[0][0], 0);
  assert.ok(Math.abs(back.at(-1)[0] - 3) < 0.1);
});

test('only plain recording file names can be downloaded', () => {
  const rec = new Recorder({ dir: tmp() });
  fs.writeFileSync(path.join(rec.dir, 'hinigram_rx1_20261024_120000.csv'), 'x');
  assert.ok(rec.file('hinigram_rx1_20261024_120000.csv'));
  assert.equal(rec.file('../package.json'), null);
  assert.equal(rec.file('..\\secrets.csv'), null);
  assert.equal(rec.file('missing.csv'), null);
  assert.equal(rec.list().length, 1);
});
