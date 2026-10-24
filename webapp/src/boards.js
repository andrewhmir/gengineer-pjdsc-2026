'use strict';

// The Boards panel's back end: lists the ESP32s on USB, tells what each one runs by reading its start-up log
// (nothing is written), and writes a chosen firmware version for a chosen role with esptool. Every built version is
// kept in the firmware library (webapp/.firmware/library, from tools/build-firmware.js); the firmware sources are
// never changed. The universal set runs one transmitter image on every board and gives each its own ID over USB.

const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { EventEmitter } = require('node:events');
const { ESP_VENDORS } = require('./receiver');

const REPO = path.resolve(__dirname, '..', '..');
const CACHE = path.resolve(__dirname, '..', '.firmware');
const LIBRARY = path.join(CACHE, 'library');
const MAX_ID = 254; // a node sends from 1a:00:00:00:00:<ID>, and 0 and 255 are not used

// What each firmware set writes for each role. A fixed set has one image per transmitter ID it was written for;
// the universal set has one transmitter image for any ID, which the board keeps in its own flash.
const SETS = {
  team: { label: 'Team firmware: csi_rx, csi_tx1 to csi_tx3', source: 'team', rx: 'csi_rx', tx: (id) => `csi_tx${id}`, ids: [1, 2, 3] },
  bundle: { label: 'v1.3.3 bundle firmware: hinigram_receiver, hinigram_node 1 to 3', source: 'bundle', rx: 'hinigram_receiver', tx: () => 'hinigram_node', ids: [1, 2, 3] },
  universal: { label: 'Universal firmware: hinigram_receiver, hinigram_universal_node for any number of transmitters', source: 'team', rx: 'hinigram_receiver', tx: () => 'hinigram_universal_node', ids: null },
};
const CHIPS = { '10c4': 'Silicon Labs CP210x', '1a86': 'WCH CH340', '0403': 'FTDI', '303a': 'Espressif USB' };

/** The image a set has for a role: 'rx', 'tx<ID>' in a fixed set, 'tx' in the universal set. */
function imageKey(set, role, id) {
  if (role === 'rx') return 'rx';
  return SETS[set].ids ? `tx${id}` : 'tx';
}

function label(role, id) {
  return role === 'rx' ? 'Receiver' : `Transmitter ${id}`;
}

/**
 * The firmware folder holding the team's csi_* projects: HINIGRAM_FIRMWARE, then <repo>/firmware, then the
 * firmware/ folder of any other checkout (git worktree) of this repository, such as one on a firmware branch.
 */
function findFirmwareDir() {
  const dirs = [process.env.HINIGRAM_FIRMWARE, path.join(REPO, 'firmware')].filter(Boolean);
  try {
    const list = spawnSync('git', ['-C', REPO, 'worktree', 'list', '--porcelain'], { encoding: 'utf8', windowsHide: true }).stdout || '';
    for (const m of list.matchAll(/^worktree (.+)$/gm)) dirs.push(path.join(m[1].trim(), 'firmware'));
  } catch {
    /* git not available: only the first two */
  }
  return dirs.find((d) => ['csi_rx', 'csi_tx1', 'csi_tx2', 'csi_tx3'].every((p) => fs.existsSync(path.join(d, p)))) || null;
}

/** Chip MAC -> "RX" / "TX2", from the "MAC:" line each csi_* README records for the board the team set up. */
function teamLabels(dir) {
  const out = {};
  if (!dir) return out;
  for (const [project, short] of [['csi_rx', 'RX'], ['csi_tx1', 'TX1'], ['csi_tx2', 'TX2'], ['csi_tx3', 'TX3']]) {
    try {
      const m = /^- MAC:\s*([0-9a-f:]{17})/im.exec(fs.readFileSync(path.join(dir, project, 'README.md'), 'utf8'));
      if (m) out[m[1].toLowerCase()] = short;
    } catch {
      /* no README */
    }
  }
  return out;
}

/** What a start-up log says the board is: its role, transmitter ID, firmware set and version. */
function parseBootLog(text) {
  const t = text.replace(/\x1b\[[0-9;]*m/g, '');
  const pick = (re) => { const m = re.exec(t); return m ? m[1].trim() : null; };
  const named = pick(/Project name:\s*(\S+)/);
  const idf = pick(/ESP-IDF:\s*(\S+)/) || pick(/, IDF (v\S+)/) || pick(/ESP-IDF (v[\d.]+\S*) 2nd stage bootloader/);
  const version = pick(/universal v([0-9A-Za-z.+-]+),/);
  const chipMac = (pick(/wifi:mode\s*:\s*sta\s*\(([0-9a-f:]{17})\)/i) || pick(/chip ([0-9a-f:]{17})/i) || '').toLowerCase() || null;
  const sendsAs = (pick(/mac:\s*(1a:00:00:00:00:[0-9a-f]{2})/i) || pick(/from (1a:00:00:00:00:[0-9a-f]{2})/i) || '').toLowerCase() || null;
  const node = pick(/node (\d+) sending/);
  const csi = /CSI_DATA,/.test(t);
  let role = null, id = null, set = null, project = named;
  const team = /^csi_(rx|tx(\d+))$/.exec(named || '');
  if (team) [role, id, set] = [team[2] ? 'tx' : 'rx', team[2] ? Number(team[2]) : null, 'team'];
  // the bundle's and the universal firmware log at WARN: they name themselves by their status or start-up lines
  else if (named === 'hinigram_receiver' || /HINIGRAM_RX,/.test(t)) [role, set, project] = ['rx', 'hinigram', 'hinigram_receiver'];
  else if (node || version || named === 'hinigram_node') {
    [role, id, set, project] = ['tx', node ? Number(node) : null, version ? 'universal' : 'bundle', version ? 'hinigram_universal_node' : 'hinigram_node'];
  }
  const runs = role === 'rx' ? 'rx' : role === 'tx' ? `tx${id === null ? '?' : id}` : csi ? 'a CSI receiver' : null;
  return { project, idf, version, chipMac, sendsAs, role, id, set, idStored: version ? /id stored/.test(t) : null, runs, csi, booted: /rst:0x|boot:|ets /.test(t) };
}

/** Python with esptool: HINIGRAM_ESPTOOL_PYTHON, then ESP-IDF's own environment, then python on PATH. */
function findEsptool() {
  const tries = [];
  if (process.env.HINIGRAM_ESPTOOL_PYTHON) tries.push(process.env.HINIGRAM_ESPTOOL_PYTHON);
  const envs = process.platform === 'win32' ? 'C:\\Espressif\\python_env' : path.join(process.env.HOME || '', '.espressif', 'python_env');
  try {
    for (const d of fs.readdirSync(envs)) tries.push(path.join(envs, d, process.platform === 'win32' ? 'Scripts\\python.exe' : 'bin/python'));
  } catch {
    /* no ESP-IDF environment */
  }
  tries.push('python', 'python3');
  for (const py of tries) {
    const r = spawnSync(py, ['-m', 'esptool', 'version'], { encoding: 'utf8', timeout: 20000, windowsHide: true });
    if (r.status === 0) return { python: py, version: (r.stdout.match(/v?\d+\.\d+\.\d+/) || [''])[0] };
  }
  return null;
}

/** Every built firmware version, newest first: [{key, set, version, builtAt, idfVersion, source, images}]. */
function readLibrary(dir = LIBRARY) {
  try {
    const list = JSON.parse(fs.readFileSync(path.join(dir, 'index.json'), 'utf8'));
    return list.filter((e) => SETS[e.set]).sort((a, b) => b.builtAt.localeCompare(a.builtAt));
  } catch {
    return [];
  }
}

/** Reads one esptool output line into a progress event, or null. */
function esptoolEvent(line) {
  let m;
  const bootHint = /Wrong boot mode|Failed to connect|Timed out waiting for packet header/i.test(line);
  if ((m = /A fatal error occurred: (.+)$/.exec(line))) return { error: m[1], ...(bootHint ? { needBoot: true } : {}) };
  if (/^Connecting/.test(line)) return { phase: 'connecting' };
  if (bootHint) return { phase: 'connecting', needBoot: true, message: line };
  if ((m = /^Chip is (.+)$/.exec(line))) return { chip: m[1] };
  if ((m = /^MAC: ([0-9a-f:]{17})/i.exec(line))) return { flashedMac: m[1].toLowerCase() };
  if ((m = /^Writing at 0x[0-9a-f]+\.*\s*\((\d+)\s*%\)/i.exec(line))) return { phase: 'writing', pct: Number(m[1]) };
  if (/Hash of data verified/.test(line)) return { phase: 'verified' };
  return null;
}

const BOOT_HINT_MS = 3500; // no reply by then: the board is probably one that needs BOOT held to be written

/** Runs esptool write_flash; resolves to {ok, error}. onEvent gets the parsed progress events. */
function writeImage({ esptool, port, image, baud, onEvent }) {
  return new Promise((resolve) => {
    const args = ['-m', 'esptool', '--chip', 'esp32', '-p', port, '-b', String(baud), '--before', 'default_reset',
      '--after', 'hard_reset', '--connect-attempts', '90', 'write_flash', '-z', '0x0', image];
    const child = spawn(esptool.python, args, { windowsHide: true });
    let error = null, tail = '', answered = false;
    const recent = []; // the last lines, for an error esptool words in some other way
    // "Connecting...." grows on one line until esptool gives up, so waiting for whole lines would show nothing
    const bootTimer = setTimeout(() => !answered && onEvent({ phase: 'connecting', needBoot: true }), BOOT_HINT_MS);
    const handle = (line) => {
      recent.push(line);
      if (recent.length > 4) recent.shift();
      const ev = esptoolEvent(line);
      if (!ev) return;
      if (ev.chip || ev.phase === 'writing') answered = true;
      if (ev.error) error = ev.error;
      onEvent(ev);
    };
    const onData = (chunk) => {
      const parts = (tail + chunk.toString('latin1')).split(/[\r\n]+/);
      tail = parts.pop();
      parts.map((l) => l.trim()).filter(Boolean).forEach(handle);
    };
    child.stdout.on('data', onData);
    child.stderr.on('data', onData);
    child.on('error', (e) => {
      clearTimeout(bootTimer);
      resolve({ ok: false, error: e.message });
    });
    child.on('close', (code) => {
      clearTimeout(bootTimer);
      if (tail.trim()) handle(tail.trim()); // the last line often has no newline, and it is usually the reason
      const why = error || recent.filter((l) => !/^Connecting/.test(l)).pop() || `esptool exited with code ${code}`;
      resolve({ ok: code === 0, error: code === 0 ? null : why });
    });
  });
}

/** Opens a port at 115,200 baud, optionally resets the board, optionally sends a line, and returns what it printed. */
function talk(SerialPort, port, { reset = false, send = null, ms = 3500, until = null } = {}) {
  return new Promise((resolve, reject) => {
    const p = new SerialPort({ path: port, baudRate: 115200, autoOpen: false, rtscts: false, hupcl: false });
    let buf = '', done = false;
    const finish = () => {
      if (done) return;
      done = true;
      p.close(() => resolve(buf));
    };
    p.open((err) => {
      if (err) return reject(err);
      p.on('data', (c) => {
        buf += c.toString('latin1');
        if (until && until.test(buf)) setTimeout(finish, 200);
      });
      p.set({ dtr: false, rts: reset }, () => reset && setTimeout(() => p.set({ dtr: false, rts: false }, () => {}), 120));
      if (send) setTimeout(() => p.write(`\r\n${send}\r\n`), 1200); // after a restart the board needs about a second
      setTimeout(finish, ms);
    });
  });
}

/** Resets a board through RTS and reads its start-up log at each speed until it says what it is. */
async function identify(SerialPort, port) {
  let found = { booted: false };
  for (const baudRate of [115200, 921600]) {
    const text = await new Promise((resolve, reject) => {
      const p = new SerialPort({ path: port, baudRate, autoOpen: false, rtscts: false, hupcl: false });
      let buf = '';
      p.open((err) => {
        if (err) return reject(err);
        p.on('data', (c) => (buf += c.toString('latin1')));
        p.set({ dtr: false, rts: true }, () => setTimeout(() => p.set({ dtr: false, rts: false }, () => {}), 120));
        setTimeout(() => p.close(() => resolve(buf)), 3500);
      });
    });
    const info = parseBootLog(text);
    if (info.booted || info.project) found = { ...info, baud: baudRate };
    if (info.runs) return found;
  }
  return found;
}

class BoardManager extends EventEmitter {
  constructor({ receiver = null, firmwareDir = findFirmwareDir(), SerialPort = null, library = LIBRARY } = {}) {
    super();
    this.receiver = receiver;
    this.firmwareDir = firmwareDir;
    this.SerialPort = SerialPort;
    this.library = library;
    this.known = new Map(); // port -> {identity, at}
    this.job = null;
    this.esptool = undefined; // found on first use: running Python takes a moment
  }

  serialPort() {
    if (!this.SerialPort) this.SerialPort = require('serialport').SerialPort;
    return this.SerialPort;
  }

  /** The lowest transmitter ID no board on USB and no transmitter on air is using. */
  nextId(heard = []) {
    const used = new Set(heard);
    for (const { identity } of this.known.values()) if (identity.role === 'tx' && identity.id) used.add(identity.id);
    for (let id = 1; id <= MAX_ID; id++) if (!used.has(id)) return id;
    return null;
  }

  async list({ heard = [] } = {}) {
    const ports = await this.serialPort().list();
    const labels = teamLabels(this.firmwareDir);
    const live = this.receiver && this.receiver.state && this.receiver.state.state === 'connected' ? this.receiver.state.path : null;
    const boards = ports
      .filter((p) => ESP_VENDORS.has(String(p.vendorId || '').toLowerCase()))
      .map((p) => {
        const k = this.known.get(p.path);
        const id = k ? k.identity : null;
        return {
          path: p.path, chip: CHIPS[String(p.vendorId).toLowerCase()] || p.manufacturer || 'USB serial', liveReceiver: p.path === live,
          identity: id, identifiedAt: k ? k.at : null, teamLabel: id && id.chipMac ? labels[id.chipMac] || null : null,
        };
      });
    const sets = Object.fromEntries(Object.entries(SETS).map(([k, s]) => [k, { label: s.label, ids: s.ids, rx: s.rx, tx: s.tx('<ID>') }]));
    const versions = readLibrary(this.library).map((e) => ({ key: e.key, set: e.set, version: e.version, builtAt: e.builtAt, idfVersion: e.idfVersion, images: Object.keys(e.images) }));
    return { boards, sets, versions, nextId: this.nextId(heard), job: this.job, firmwareDir: this.firmwareDir };
  }

  /** Tells the receiver search to leave transmitters alone: opening their port to look for CSI resets them. */
  remember(port, identity) {
    this.known.set(port, { identity, at: Date.now() / 1000 });
    if (!this.receiver) return;
    this.receiver.skip = new Set([...this.known].filter(([, k]) => k.identity.role === 'tx').map(([p]) => p));
  }

  setJob(patch) {
    this.job = { ...this.job, ...patch, updated: Date.now() / 1000 };
    this.emit('job', this.job);
  }

  /** Runs fn with the live receiver let go of its port, so a board operation can open any port. */
  async withPortsFree(fn) {
    if (this.busy) throw new Error('Another board operation is running.');
    this.busy = true;
    try {
      if (this.receiver && this.receiver.pause) await this.receiver.pause();
      return await fn();
    } finally {
      if (this.receiver && this.receiver.resume) this.receiver.resume();
      this.busy = false;
    }
  }

  async identify(port) {
    return this.withPortsFree(async () => {
      const identity = await identify(this.serialPort(), port);
      this.remember(port, identity);
      return identity;
    });
  }

  /** Gives a board running the universal firmware a new transmitter ID, without writing firmware. */
  async storeId(port, id) {
    const out = await talk(this.serialPort(), port, { send: `hinigram id ${id}`, ms: 5000, until: /id set to \d+|refused|could not be stored/ });
    const m = /id set to (\d+)|(refused|could not be stored)/.exec(out);
    if (!m || m[2]) throw new Error(m ? `The board ${m[2] === 'refused' ? 'refused' : 'could not store'} ID ${id}` : 'The board did not answer. Does it run the universal firmware?');
    await new Promise((r) => setTimeout(r, 1200)); // it restarts with the new ID
    const identity = await identify(this.serialPort(), port);
    this.remember(port, identity);
    if (identity.id !== id) throw new Error(`The board now reports ID ${identity.id}, not ${id}`);
    return identity;
  }

  async setId(port, id) {
    if (!(id >= 1 && id <= MAX_ID)) throw new Error(`An ID is 1 to ${MAX_ID}`);
    return this.withPortsFree(() => this.storeId(port, id));
  }

  /**
   * Writes the image for a role (and transmitter ID) from a library version to the board on `port`, then reads its
   * start-up log to check it. For the universal set the ID is then stored on the board over USB.
   */
  async flash(port, { role, id = null, version }) {
    if (/^tx\d+$/.test(role)) [role, id] = ['tx', Number(role.slice(2))]; // the older "tx2" form
    if (!['rx', 'tx'].includes(role)) throw new Error(`unknown role ${role}`);
    const lib = readLibrary(this.library);
    const entry = version ? lib.find((e) => e.key === version) : lib[0];
    if (!entry) throw new Error(version ? `No firmware version ${version} in the library` : 'The firmware library is empty. Run: node tools/build-firmware.js');
    const set = SETS[entry.set];
    if (role === 'tx') {
      id = Number(id);
      if (!(id >= 1 && id <= MAX_ID)) throw new Error(`A transmitter ID is 1 to ${MAX_ID}`);
      if (set.ids && !set.ids.includes(id)) throw new Error(`${entry.set} firmware has transmitters ${set.ids.join(', ')} only. Use the universal firmware for ID ${id}.`);
    }
    const image = entry.images[imageKey(entry.set, role, id)];
    if (!image) throw new Error(`${entry.key} has no image for ${label(role, id)}`);
    if (this.esptool === undefined) this.esptool = findEsptool();
    if (!this.esptool) throw new Error('esptool was not found. Install ESP-IDF, or pip install esptool.');
    const project = role === 'rx' ? set.rx : set.tx(id);
    const before = this.known.get(port);
    this.job = { port, role, id, version: entry.key, label: `${label(role, id)} (${project} ${entry.version})`, phase: 'starting', pct: 0, needBoot: false, message: 'Starting', started: Date.now() / 1000, before: before ? before.identity : null };
    this.emit('job', this.job);
    this.withPortsFree(async () => {
      for (const baud of [460800, 115200]) {
        this.setJob({ phase: 'connecting', pct: 0, baud, message: `Connecting at ${baud.toLocaleString('en-US')} baud` });
        const res = await writeImage({
          esptool: this.esptool, port, image: path.join(this.library, image.file), baud,
          onEvent: (ev) => {
            if (ev.phase === 'writing' || ev.chip) ev.needBoot = false;
            this.setJob(ev);
          },
        });
        if (res.ok) {
          this.setJob({ phase: 'checking', pct: 100, needBoot: false, message: 'Written and verified. Reading what the board now runs' });
          await new Promise((r) => setTimeout(r, 1500));
          let identity = await identify(this.serialPort(), port);
          this.remember(port, identity);
          if (identity.project === project && role === 'tx' && !set.ids && identity.id !== id) {
            this.setJob({ message: `Giving it transmitter ID ${id}` });
            identity = await this.storeId(port, id);
          }
          const ok = identity.project === project && identity.role === role && (role === 'rx' || identity.id === id);
          return this.setJob({ phase: ok ? 'done' : 'failed', identity, message: ok ? `Now runs ${project} as ${label(role, id)}` : `Written, but after a reset the board reports ${identity.project || 'nothing'}${identity.runs ? ` (${identity.runs})` : ''}` });
        }
        const retry = baud !== 115200 && /stopped responding|Timed out|Packet content/i.test(res.error || '') && this.job.phase === 'writing';
        if (!retry) return this.setJob({ phase: 'failed', needBoot: false, message: res.error });
        this.setJob({ message: `${res.error}. Trying again at 115,200 baud` });
      }
    }).catch((e) => this.setJob({ phase: 'failed', message: e.message }));
    return this.job;
  }
}

module.exports = { BoardManager, SETS, CACHE, LIBRARY, MAX_ID, imageKey, parseBootLog, esptoolEvent, teamLabels, findFirmwareDir, findEsptool, readLibrary };
