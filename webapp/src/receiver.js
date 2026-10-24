'use strict';

const { EventEmitter } = require('node:events');
const { LineSplitter } = require('./lines');

// USB-serial chips found on ESP32 boards: Silicon Labs CP210x, WCH CH340/CH9102, FTDI, Espressif native USB.
const ESP_VENDORS = new Set(['10c4', '1a86', '0403', '303a']);
const PROBE_MS = 3500; // a receiver with a transmitter in range prints CSI_DATA many times a second
const RETRY_MS = 2000;
// Opening a port resets the board on it, so a port that proved silent is not tried again for a while:
// a transmitter plugged in to this computer would otherwise restart every few seconds and send nothing.
const SILENT_BACKOFF_S = 30;
const SILENT_BACKOFF_LAST_GOOD_S = 5;

function loadSerialPort() {
  // Required lazily so the demo and replay sources, and the tests, run without the native module.
  return require('serialport').SerialPort;
}

/**
 * Opens a port with DTR and RTS held low. On ESP32 boards these lines drive EN and BOOT through the
 * auto-reset circuit, and with RTS high some boards are held in reset and send nothing.
 */
function openPort(SerialPort, path, baudRate) {
  return new Promise((resolve, reject) => {
    const port = new SerialPort({ path, baudRate, autoOpen: false, rtscts: false, hupcl: false });
    port.open((err) => {
      if (err) return reject(err);
      port.set({ dtr: false, rts: false }, () => resolve(port)); // an adapter without control lines is fine too
    });
  });
}

function closePort(port) {
  return new Promise((resolve) => {
    if (!port || !port.isOpen) return resolve();
    port.close(() => resolve());
  });
}

// A receiver prints CSI_DATA only while a transmitter is heard, so its start-up banner counts too.
const RECEIVER_SIGN = /CSI_DATA,|Project name:\s+(csi_rx|hinigram_receiver)\b|HINIGRAM_RX,/;

/**
 * Restarts the board on a port and listens briefly: 'receiver' when it prints a receiver's banner or CSI_DATA,
 * 'busy' when another program has the port, 'silent' otherwise.
 */
async function probe(SerialPort, path, baudRate, ms = PROBE_MS) {
  let port;
  try {
    port = await openPort(SerialPort, path, baudRate);
  } catch (e) {
    return /access denied|busy|in use/i.test(e.message) ? 'busy' : 'gone';
  }
  const split = new LineSplitter();
  const found = await new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), ms);
    port.on('data', (chunk) => {
      if (split.push(chunk).some((l) => RECEIVER_SIGN.test(l))) {
        clearTimeout(timer);
        resolve(true);
      }
    });
    port.on('error', () => resolve(false));
    port.set({ dtr: false, rts: true }, () => setTimeout(() => port.set({ dtr: false, rts: false }, () => {}), 120)); // reset: EN low, then run
  });
  await closePort(port);
  return found ? 'receiver' : 'silent';
}

/** Candidate ports, the last good one first. */
function candidates(ports, preferred) {
  const esp = ports.filter((p) => ESP_VENDORS.has(String(p.vendorId || '').toLowerCase()));
  esp.sort((a, b) => (b.path === preferred) - (a.path === preferred));
  return esp.map((p) => p.path);
}

/**
 * The receiver on a serial port. Emits `line` (text, host time in seconds) and `status` objects:
 * {state: 'searching' | 'connected' | 'disconnected', path, baud, message}.
 */
class SerialReceiver extends EventEmitter {
  constructor({ path = null, baud = 921600 } = {}) {
    super();
    this.fixedPath = path;
    this.baud = baud;
    this.lastGood = path;
    this.port = null;
    this.stopped = false;
    this.paused = false;
    this.holding = 0; // ports this receiver has open right now, probes included
    this.skip = new Set(); // ports the Boards panel identified as transmitters
    this.silentUntil = new Map(); // port -> time (s) before which it is not probed again
    this.kind = 'serial';
  }

  /** Lets go of every port until resume(), for the Boards panel to identify or flash a board. */
  async pause() {
    this.paused = true;
    await closePort(this.port);
    for (let i = 0; i < 60 && this.holding > 0; i++) await new Promise((r) => setTimeout(r, 100));
    this.status('paused', { message: 'Paused while a board is set up' });
  }

  resume() {
    this.paused = false;
  }

  start() {
    this.loop();
    return this;
  }

  async stop() {
    this.stopped = true;
    await closePort(this.port);
  }

  status(state, extra = {}) {
    this.state = Object.assign({ state, path: this.port ? this.port.path : null, baud: this.baud }, extra);
    this.emit('status', this.state);
  }

  async findPath(SerialPort) {
    if (this.fixedPath) return this.fixedPath;
    const listed = await SerialPort.list();
    const now = Date.now() / 1000;
    const all = candidates(listed, this.lastGood);
    const paths = all.filter((p) => !this.skip.has(p) && !(this.silentUntil.get(p) > now));
    const skipped = all.filter((p) => this.skip.has(p));
    let message = paths.length ? `Looking for the receiver on ${paths.join(', ')}` : all.length ? 'Waiting for the receiver' : 'No ESP32 is connected to this computer';
    if (skipped.length) message += ` (${skipped.join(', ')}: a transmitter, left alone)`;
    this.status('searching', { message, ports: all });
    const busy = [];
    for (const p of paths) {
      if (this.stopped || this.paused) return null;
      this.holding++;
      const found = await probe(SerialPort, p, this.baud).finally(() => this.holding--);
      if (found === 'receiver') return p;
      if (found === 'busy') busy.push(p);
      if (found === 'silent') this.silentUntil.set(p, Date.now() / 1000 + (p === this.lastGood ? SILENT_BACKOFF_LAST_GOOD_S : SILENT_BACKOFF_S));
    }
    if (busy.length) {
      this.status('searching', {
        ports: paths,
        message: `${busy.join(' and ')} ${busy.length > 1 ? 'are' : 'is'} in use by another program. Close the v1.3.3 board tab, a serial monitor or log_serial.py, and the console connects by itself.`,
      });
    }
    return null;
  }

  async loop() {
    let SerialPort;
    try {
      SerialPort = loadSerialPort();
    } catch (e) {
      this.status('disconnected', { message: `The serialport module is not installed (${e.message}). Run npm ci in webapp/.` });
      return;
    }
    while (!this.stopped) {
      if (this.paused) {
        await new Promise((r) => setTimeout(r, 250));
        continue;
      }
      const path = await this.findPath(SerialPort).catch(() => null);
      if (path && !this.stopped && !this.paused) {
        this.holding++;
        try {
          this.port = await openPort(SerialPort, path, this.baud);
          this.lastGood = path;
          this.status('connected', { message: `Receiver on ${path} at ${this.baud.toLocaleString('en-US')} baud` });
          await this.pump(this.port);
        } catch (e) {
          this.status('disconnected', { message: `Could not open ${path}: ${e.message}` });
        }
        await closePort(this.port);
        this.port = null;
        this.holding--;
        if (!this.stopped && !this.paused) this.status('disconnected', { message: `Lost the receiver on ${path}; reconnecting` });
      }
      if (!this.stopped && !this.paused) await new Promise((r) => setTimeout(r, RETRY_MS));
    }
  }

  pump(port) {
    const split = new LineSplitter();
    return new Promise((resolve) => {
      port.on('data', (chunk) => {
        const t = Date.now() / 1000;
        for (const line of split.push(chunk)) this.emit('line', line, t);
      });
      port.on('close', resolve);
      port.on('error', resolve);
    });
  }
}

module.exports = { SerialReceiver, candidates, probe, openPort, ESP_VENDORS, RECEIVER_SIGN };
