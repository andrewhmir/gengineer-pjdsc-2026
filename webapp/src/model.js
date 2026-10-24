'use strict';

// The ResoNet second opinion: the v1.3.3 bundle's trained models (training/mlruns, variant lin_sync-e80),
// run by model/resonet_sidecar.py with Python next to the console. Display only: its readings never change a
// status or an alert. Without Python, jax or the bundle the console runs as before and says why.

const { spawn } = require('node:child_process');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const { LineSplitter } = require('./lines');

const SCRIPT = path.resolve(__dirname, '..', 'model', 'resonet_sidecar.py');
const DEFAULT_BUNDLE = path.resolve(__dirname, '..', '..', 'Hinigram other versions', 'Hinigram_v1.3.3');
const MAX_QUEUED = 8 * 1024 * 1024; // lines waiting for the helper; beyond this it has fallen behind and lines drop

class ModelSidecar extends EventEmitter {
  /** `command` replaces the Python helper (tests use it): [executable, args]. */
  constructor({ bundle = process.env.HINIGRAM_BUNDLE || DEFAULT_BUNDLE, python = process.env.HINIGRAM_PYTHON || 'python', command = null } = {}) {
    super();
    this.bundle = bundle;
    this.python = python;
    this.command = command;
    this.child = null;
    this.dropped = 0;
    this.state = { state: 'off', message: 'Model estimate is off' };
  }

  setState(state, message, extra = {}) {
    this.state = { state, message, ...extra };
    this.emit('state', this.state);
  }

  start() {
    if (!this.command && !fs.existsSync(path.join(this.bundle, 'training', 'mlruns'))) {
      this.setState('unavailable', `The v1.3.3 bundle is not at ${this.bundle}. Start with --bundle <folder> or set HINIGRAM_BUNDLE.`);
      return this;
    }
    const [cmd, args] = this.command || [this.python, [SCRIPT, '--bundle', this.bundle]];
    this.setState('starting', 'Loading the six ResoNet models');
    let lastError = null;
    const child = (this.child = spawn(cmd, args, { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true }));
    child.on('error', (e) => this.setState('unavailable', `Could not start ${cmd}: ${e.message}. Set HINIGRAM_PYTHON to a Python with jax.`));
    child.on('exit', (code) => {
      this.child = null;
      if (this.state.state !== 'unavailable' && !this.stopping) this.setState('unavailable', lastError || `The model helper stopped (exit code ${code}).`);
    });
    child.stdin.on('error', () => {}); // the helper exited; its exit handler reports why
    child.stderr.on('data', () => {}); // jax's start-up warnings
    const split = new LineSplitter();
    child.stdout.on('data', (chunk) => {
      for (const line of split.push(chunk)) {
        let msg;
        try {
          msg = JSON.parse(line);
        } catch {
          continue;
        }
        if (msg.type === 'ready') this.setState('ready', `ResoNet ${msg.variant}, ${msg.n_models} models`, { variant: msg.variant, models: msg.n_models });
        else if (msg.type === 'estimate') this.emit('estimate', msg);
        else if (msg.type === 'error') lastError = msg.message;
      }
    });
    return this;
  }

  send(line) {
    const c = this.child;
    if (!c || !c.stdin.writable || this.state.state === 'unavailable') return;
    if (c.stdin.writableLength > MAX_QUEUED) {
      this.dropped++;
      return;
    }
    c.stdin.write(`${line}\n`);
  }

  setProfile(mac, profile) {
    this.send(`#profile ${mac} ${profile}`);
  }

  reset() {
    this.send('#reset');
  }

  async stop() {
    this.stopping = true;
    if (this.child) this.child.kill();
  }
}

module.exports = { ModelSidecar, DEFAULT_BUNDLE };
