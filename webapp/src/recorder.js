'use strict';

// Records the receiver's lines in the format of the bundle's firmware/tools/log_serial.py: one line per record,
// `<host time, s, 6 decimals>,<CSI_DATA or HINIGRAM_RX line>`. The v1.3.3 board ("Open a CSV file") and
// hinigram_live.load_csi_session read it. Recordings are local data: they go to data/raw/, which git ignores.

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_DIR = path.resolve(__dirname, '..', '..', 'data', 'raw', 'recordings');
const NAME = /^[A-Za-z0-9_.-]+\.csv$/;

function stamp(d = new Date()) {
  const p = (x) => String(x).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function formatLine(t, text) {
  return `${t.toFixed(6)},${text}\n`;
}

class Recorder {
  constructor({ dir = DEFAULT_DIR } = {}) {
    this.dir = dir;
    this.out = null;
  }

  /** Starts a new file. `kind` marks where the data came from: rx1 for the receiver, sim for simulated data. */
  start(kind = 'rx1') {
    if (this.out) return this.state();
    fs.mkdirSync(this.dir, { recursive: true });
    this.name = `hinigram_${kind}_${stamp()}.csv`;
    this.out = fs.createWriteStream(path.join(this.dir, this.name), { flags: 'a', encoding: 'latin1' });
    this.lines = 0;
    this.bytes = 0;
    this.startedAt = Date.now() / 1000;
    return this.state();
  }

  write(t, text) {
    if (!this.out) return;
    const s = formatLine(t, text);
    this.out.write(s);
    this.lines++;
    this.bytes += s.length;
  }

  stop() {
    if (!this.out) return this.state();
    const done = { name: this.name, lines: this.lines, bytes: this.bytes };
    this.out.end();
    this.out = null;
    return Object.assign(this.state(), { saved: done });
  }

  state() {
    return this.out
      ? { on: true, name: this.name, lines: this.lines, bytes: this.bytes, seconds: Math.round(Date.now() / 1000 - this.startedAt) }
      : { on: false };
  }

  list() {
    let names = [];
    try {
      names = fs.readdirSync(this.dir).filter((n) => NAME.test(n));
    } catch {
      return [];
    }
    return names
      .map((name) => {
        const st = fs.statSync(path.join(this.dir, name));
        return { name, bytes: st.size, modified: st.mtimeMs / 1000 };
      })
      .sort((a, b) => b.modified - a.modified);
  }

  /** The full path of a recording named by the UI, or null when the name is not a plain recording file name. */
  file(name) {
    if (!NAME.test(name)) return null;
    const p = path.join(this.dir, name);
    return fs.existsSync(p) ? p : null;
  }
}

module.exports = { Recorder, formatLine, DEFAULT_DIR };
