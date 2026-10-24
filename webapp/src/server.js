'use strict';

// Hinigram live console. One process: reads the receiver (or the simulator, or a recording), runs the
// pipeline, records on request, and serves the UI and its JSON API on localhost.

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { spawn } = require('node:child_process');

const { Monitor } = require('./monitor');
const { Recorder } = require('./recorder');
const { recordOf, droppedOf, loggedOf } = require('./lines');

const PUBLIC = path.resolve(__dirname, '..', 'public');
const STATIC = {
  '/': ['index.html', 'text/html; charset=utf-8'],
  '/app.js': ['app.js', 'text/javascript; charset=utf-8'],
  '/app.css': ['app.css', 'text/css; charset=utf-8'],
  '/boards.js': ['boards.js', 'text/javascript; charset=utf-8'],
  '/icon.svg': ['icon.svg', 'image/svg+xml'],
  '/fonts/AtkinsonHyperlegibleNext.ttf': ['fonts/AtkinsonHyperlegibleNext.ttf', 'font/ttf'],
  '/fonts/OFL.txt': ['fonts/OFL.txt', 'text/plain; charset=utf-8'],
};
const PUSH_MS = 1000;
const MAX_BODY = 4096;

/**
 * Wires a source (SerialReceiver, DemoReceiver or ReplayReceiver) to the pipeline, the recorder and, when there
 * is one, the ResoNet helper, whose readings are kept beside the pipeline's and never mixed into them.
 */
function connect(source, monitor, recorder, model) {
  const live = { status: { state: 'searching', message: 'Starting' } };
  source.on('status', (s) => (live.status = s));
  source.on('restart', () => {
    monitor.reset();
    if (model) model.reset();
  });
  source.on('line', (line, t) => {
    monitor.line(line, t);
    const dropped = droppedOf(line), logged = loggedOf(line);
    if (dropped !== null) monitor.counts.dropped = dropped;
    if (logged !== null) monitor.counts.logged = logged; // the bundle receiver's own tally, once a minute
    const rec = recordOf(line);
    if (!rec) return;
    if (rec.kind === 'CSI_DATA') {
      monitor.ingest(rec.text, t);
      if (model) model.send(rec.text);
    }
    recorder.write(t, rec.text);
  });
  if (model) {
    monitor.modelState = model.state;
    model.on('state', (s) => (monitor.modelState = s));
    model.on('estimate', (est) => monitor.setModel(est.mac, est));
  }
  return live;
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (c) => {
      body += c;
      if (body.length > MAX_BODY) reject(new Error('body too large'));
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        reject(new Error('body is not JSON'));
      }
    });
  });
}

function send(res, code, body, type = 'application/json; charset=utf-8') {
  res.writeHead(code, { 'Content-Type': type, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
  res.end(typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body));
}

function createServer({ source, monitor = new Monitor(), recorder = new Recorder(), model = null, boards = null }) {
  const live = connect(source, monitor, recorder, model);
  const recKind = source.kind === 'demo' ? 'sim' : source.kind === 'replay' ? 'replay' : 'rx1';
  const snapshot = () => ({
    ...monitor.snapshot({ ...live.status, source: source.kind }, recorder.state()),
    boardJob: boards ? boards.job : null,
  });
  /** A port the Boards panel may touch: one listed as an ESP32 USB-serial chip, nothing typed in by hand. */
  const boardPort = async (p) => {
    const { boards: list } = await boards.list();
    if (!list.some((b) => b.path === p)) throw new Error(`${p} is not an ESP32 board on USB`);
    return p;
  };
  const clients = new Set();
  const timer = setInterval(() => {
    if (!clients.size) return;
    const msg = `event: state\ndata: ${JSON.stringify(snapshot())}\n\n`;
    for (const res of clients) res.write(msg);
  }, PUSH_MS);

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const route = `${req.method} ${url.pathname}`;
    try {
      if (req.method === 'GET' && STATIC[url.pathname]) {
        const [file, type] = STATIC[url.pathname];
        return send(res, 200, fs.readFileSync(path.join(PUBLIC, file)), type);
      }
      if (route === 'GET /api/state') return send(res, 200, snapshot());
      if (route === 'GET /api/events') {
        res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', Connection: 'keep-alive' });
        res.write(`event: state\ndata: ${JSON.stringify(snapshot())}\n\n`);
        clients.add(res);
        req.on('close', () => clients.delete(res));
        return;
      }
      if (route === 'GET /api/recordings') return send(res, 200, recorder.list());
      if (req.method === 'GET' && url.pathname.startsWith('/recordings/')) {
        const file = recorder.file(decodeURIComponent(url.pathname.slice('/recordings/'.length)));
        if (!file) return send(res, 404, { error: 'no such recording' });
        res.writeHead(200, { 'Content-Type': 'text/csv; charset=latin1', 'Content-Disposition': `attachment; filename="${path.basename(file)}"` });
        return fs.createReadStream(file).pipe(res);
      }
      if (url.pathname.startsWith('/api/boards') && !boards) return send(res, 404, { error: 'the Boards panel is off' });
      if (route === 'GET /api/boards') {
        const heard = [...monitor.sensors.values()].map((s) => s.tx).filter(Boolean); // IDs on air, for the next free one
        return send(res, 200, await boards.list({ heard }));
      }
      if (route === 'POST /api/boards/set-id') {
        const { path: p, id } = await readBody(req);
        return send(res, 200, await boards.setId(await boardPort(String(p)), Number(id)));
      }
      if (route === 'POST /api/boards/identify') {
        const { path: p } = await readBody(req);
        return send(res, 200, await boards.identify(await boardPort(String(p))));
      }
      if (route === 'POST /api/boards/flash') {
        const { path: p, role, id, version } = await readBody(req);
        return send(res, 200, await boards.flash(await boardPort(String(p)), { role: String(role), id: id === undefined ? null : Number(id), version: version ? String(version) : null }));
      }
      if (route === 'POST /api/record/start') return send(res, 200, recorder.start(recKind));
      if (route === 'POST /api/record/stop') return send(res, 200, recorder.stop());
      if (route === 'POST /api/reset') {
        monitor.reset();
        if (model) model.reset();
        return send(res, 200, { ok: true });
      }
      if (route === 'POST /api/profile') {
        const body = await readBody(req);
        const mac = String(body.mac).toLowerCase(), profile = String(body.profile);
        monitor.setProfile(mac, profile);
        if (model) model.setProfile(mac, profile);
        return send(res, 200, { ok: true });
      }
      return send(res, 404, { error: 'not found' });
    } catch (e) {
      return send(res, 400, { error: e.message });
    }
  });
  // The event streams never end by themselves, so they are ended first; server.close() would wait for them.
  server.shutdown = async () => {
    clearInterval(timer);
    for (const res of clients) res.end();
    clients.clear();
    recorder.stop();
    await source.stop();
    if (model) await model.stop();
    await new Promise((resolve) => {
      server.close(() => resolve());
      server.closeAllConnections();
    });
  };
  return server;
}

function openBrowser(url) {
  const cmd = process.platform === 'win32' ? ['cmd', ['/c', 'start', '', url]] : process.platform === 'darwin' ? ['open', [url]] : ['xdg-open', [url]];
  try {
    spawn(cmd[0], cmd[1], { detached: true, stdio: 'ignore' }).unref();
  } catch {
    /* no browser to open: the URL is printed */
  }
}

const HELP = `Hinigram live console

  npm start                       find the receiver on USB and open the console
  npm start -- --port COM5        use this serial port
  npm run demo                    simulated receiver, no hardware
  npm start -- --replay FILE.csv  play a recording back

Options: --baud 921600  --http 8780  --host 127.0.0.1  --speed 1 (replay)  --recordings DIR  --no-open
         --bundle DIR (the unzipped Hinigram_v1.3.3, for the ResoNet second opinion)  --python EXE  --no-model`;

function main(argv = process.argv.slice(2)) {
  const { values } = parseArgs({
    args: argv,
    options: {
      port: { type: 'string' }, baud: { type: 'string', default: '921600' }, demo: { type: 'boolean', default: false },
      replay: { type: 'string' }, speed: { type: 'string', default: '1' }, http: { type: 'string', default: process.env.HINIGRAM_HTTP_PORT || '8780' },
      host: { type: 'string', default: '127.0.0.1' }, recordings: { type: 'string' }, 'no-open': { type: 'boolean', default: false },
      bundle: { type: 'string' }, python: { type: 'string' }, 'no-model': { type: 'boolean', default: false },
      help: { type: 'boolean', short: 'h', default: false },
    },
  });
  if (values.help) return console.log(HELP);
  let source;
  if (values.demo) source = new (require('./simulate').DemoReceiver)();
  else if (values.replay) source = new (require('./replay').ReplayReceiver)({ file: path.resolve(values.replay), speed: Number(values.speed) || 1 });
  else source = new (require('./receiver').SerialReceiver)({ path: values.port || process.env.HINIGRAM_PORT || null, baud: Number(values.baud) });
  const recorder = new Recorder(values.recordings ? { dir: path.resolve(values.recordings) } : {});
  let model = null;
  if (!values['no-model']) {
    const { ModelSidecar } = require('./model');
    const opts = {};
    if (values.bundle) opts.bundle = path.resolve(values.bundle);
    if (values.python) opts.python = values.python;
    model = new ModelSidecar(opts);
    model.on('state', (s) => console.log(`[model] ${s.message}`));
  }
  const { BoardManager } = require('./boards');
  const boards = new BoardManager({ receiver: source.kind === 'serial' ? source : null });
  boards.on('job', (j) => ['connecting', 'checking', 'done', 'failed'].includes(j.phase) && console.log(`[boards] ${j.port}: ${j.message || j.phase}`));
  const server = createServer({ source, recorder, model, boards });
  source.on('status', (s) => console.log(`[receiver] ${s.message || s.state}`));
  source.start();
  if (model) model.start();
  server.listen(Number(values.http), values.host, () => {
    const url = `http://${values.host === '0.0.0.0' ? '127.0.0.1' : values.host}:${server.address().port}/`;
    console.log(`Hinigram live console: ${url}`);
    if (values.host !== '127.0.0.1') console.log('Warning: the console is reachable from other machines on this network.');
    if (!values['no-open']) openBrowser(url);
  });
  const quit = () => server.shutdown().then(() => process.exit(0));
  process.on('SIGINT', quit);
  process.on('SIGTERM', quit);
}

if (require.main === module) main();

module.exports = { createServer, connect, main };
