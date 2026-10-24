'use strict';

// Plays a recording back through the console as if the receiver were sending it, at its own pace: by the host
// timestamps log_serial.py and the recorder put in front of each line, or, for a bare receiver log, by the
// receiver's clock in each CSI_DATA record.

const fs = require('node:fs');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { recordOf } = require('./lines');

const TS_WRAP = 4294967296;

/** [time (s, from 0), record text] for every CSI_DATA and HINIGRAM_RX line of a recording. */
function readRecording(file) {
  const out = [];
  let tsPrev = null, tsAdd = 0, t0 = null;
  for (const line of fs.readFileSync(file, 'latin1').split(/\r?\n/)) {
    const rec = recordOf(line);
    if (!rec) continue;
    const head = line.slice(0, line.indexOf(rec.kind)).replace(/,\s*$/, '');
    let t = head ? parseFloat(head) : NaN;
    if (!Number.isFinite(t) && rec.kind === 'CSI_DATA') {
      const ts = Number(rec.text.split(',')[18]); // the receiver's microsecond clock, which wraps at 2^32
      if (Number.isFinite(ts)) {
        if (tsPrev !== null && ts - tsPrev < -TS_WRAP / 2) tsAdd += TS_WRAP;
        tsPrev = ts;
        t = (ts + tsAdd) / 1e6;
      }
    }
    if (!Number.isFinite(t)) t = out.length ? out[out.length - 1][0] : 0;
    if (t0 === null) t0 = t;
    out.push([t - t0, rec.text]);
  }
  return out;
}

class ReplayReceiver extends EventEmitter {
  constructor({ file, speed = 1, loop = true }) {
    super();
    this.file = file;
    this.speed = speed;
    this.loop = loop;
    this.kind = 'replay';
  }

  start() {
    this.lines = readRecording(this.file);
    if (!this.lines.length) throw new Error(`${this.file} has no CSI_DATA lines`);
    this.state = { state: 'connected', path: path.basename(this.file), baud: null, message: `Replaying ${path.basename(this.file)} (${Math.round(this.lines.at(-1)[0])} s)` };
    setImmediate(() => this.emit('status', this.state));
    this.restart();
    this.timer = setInterval(() => this.tick(), 50);
    return this;
  }

  restart() {
    this.i = 0;
    this.wall0 = Date.now() / 1000;
  }

  tick() {
    const now = (Date.now() / 1000 - this.wall0) * this.speed;
    while (this.i < this.lines.length && this.lines[this.i][0] <= now) {
      const [t, text] = this.lines[this.i++];
      this.emit('line', text, this.wall0 + t / this.speed);
    }
    if (this.i >= this.lines.length) {
      if (!this.loop) return this.stop();
      this.emit('restart'); // a new pass: the console starts afresh rather than joining the end to the start
      this.restart();
    }
  }

  async stop() {
    clearInterval(this.timer);
  }
}

module.exports = { ReplayReceiver, readRecording };
