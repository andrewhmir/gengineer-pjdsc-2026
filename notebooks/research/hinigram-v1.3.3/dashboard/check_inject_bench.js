// Checks for the board's injection bench (hinigram_inject.js), run with Node from the bundle folder:
//     node dashboard/check_inject_bench.js [out_dir]
// 1. The packed sample decodes to exactly the packets of demo_20261019_024431.csv.
// 2. Chairs with known breathing are streamed through the board's live pipeline (HinigramDSP.LiveSession) for six
//    minutes of looped background, and readings are scored against the injected truth (30 s windows, as in the notebook).
// 3. A breath-hold is flagged, a short one is not, simulated movement is seen as movement, and an empty chair shows
//    (almost) no rate. Alerts are listed in full as episodes; a pause alert on the empty chair is reported as a known
//    open failure (notebook Part 1, Sections 6b and 7), not counted as a passed or failed check.
// 4. Writes the injected stream as a receiver CSV plus its truth log, so check_inject_bench.py can run the frozen Python
//    v1.3.2 on the same packets and report how often it gives the same states and rates (it reports; it does not pass or fail).
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const dir = __dirname, root = path.join(dir, '..');
const DSP = require(path.join(dir, 'hinigram_dsp.js'));
const INJ = require(path.join(dir, 'hinigram_inject.js'));
const outDir = process.argv[2] || path.join(root, 'inject_check');
let failures = 0, known = 0;
const check = (ok, msg) => { console.log((ok ? 'ok   ' : 'FAIL ') + msg); if (!ok) failures++; };
const knownFailure = (bad, msg) => { console.log((bad ? 'KNOWN ' : 'ok   ') + msg); if (bad) known++; };
// updates under 3 s apart (the pipeline updates every 2 s) form one episode: "152-200 s (25 updates)"
function episodes(ts) {
  const out = [];
  for (const t of ts) {
    const e = out[out.length - 1];
    if (e && t - e.b < 3) { e.b = t; e.n++; } else out.push({ a: t, b: t, n: 1 });
  }
  return out.map((e) => `${e.a.toFixed(0)}-${e.b.toFixed(0)} s (${e.n} update${e.n > 1 ? 's' : ''})`).join(', ') || 'none';
}

// ---- 1. packed sample == the CSV
const src = INJ.unpackBuffer(zlib.gunzipSync(Buffer.from(fs.readFileSync(path.join(dir, 'sample_packets.b64'), 'utf8'), 'base64')));
const lines = fs.readFileSync(path.join(root, 'demo_20261019_024431.csv'), 'utf8').split(/\r?\n/).filter((l) => l.indexOf('CSI_DATA') >= 0);
let same = lines.length === src.recs.length;
for (let i = 0; same && i < lines.length; i++) {
  const a = DSP.parseLine(lines[i]), b = src.recs[i];
  if (a.mac !== b.mac || a.seq !== b.seq || a.rssi !== b.rssi || a.ts_us !== b.ts_us || a.fwi !== b.fwi || a.channel !== b.channel) same = false;
  for (let k = 0; same && k < 128; k++) if (a.raw[k] !== b.raw[k]) same = false;
}
check(same, `packed sample decodes to the ${lines.length} packets of the CSV`);

// ---- 2-3. a bench run
const PAUSE_MIN = { adult: 10, child_1_5y: 20, infant_2_12m: 20, newborn_lt2m: 20 };
const CHAIRS = [
  { seat: 'A1', src: src.macs[0], offset: 0, profile: 'adult', depth: 0.05, script: [[0, 150, 14], [150, 400, 24]] },
  { seat: 'A2', src: src.macs[1], offset: 40, profile: 'adult', depth: 0.05, script: [[0, 100, 16], [100, 118, 0], [118, 300, 16], [300, 308, 0], [308, 400, 16]] },
  { seat: 'A3', src: src.macs[2], offset: 80, profile: 'child_1_5y', depth: 0.05, script: [[0, 400, 34]] },
  { seat: 'B1', src: src.macs[0], offset: 120, profile: 'adult', depth: 0.05, script: [[0, 400, 18]], moves: [[230, 6]] },
  { seat: 'B2', src: src.macs[1], offset: 160, profile: 'adult', depth: 0.05, empty: true },
];
const RANGE = null, RUN_S = 360;
const player = new INJ.Player(src, CHAIRS.map((c, i) => ({ mac: '1a:00:00:00:01:0' + (i + 1), src: c.src, offset: c.offset, seat: c.seat })), RANGE);
const inj = new Map(), byMac = new Map();
CHAIRS.forEach((c, i) => {
  const mac = '1a:00:00:00:01:0' + (i + 1);
  const ci = new INJ.ChairInjector(1000 + i, { depth: c.depth, script: c.script || null, scriptT0: 0, mode: c.empty ? 'empty' : 'breathing' });
  (c.moves || []).forEach(([t0, d]) => ci.move(t0, d));
  inj.set(mac, ci); byMac.set(mac, Object.assign({ mac, hops: [], truth: { t: [], bpm: [] } }, c));
});
const live = new DSP.LiveSession(Object.fromEntries(CHAIRS.map((c, i) => ['1a:00:00:00:01:0' + (i + 1), c.profile])));
const csv = [], T_HOST0 = 1792349072.0, TS0 = 100000000;
const t0 = Date.now();
for (const p of player.until(RUN_S)) {
  const mac = p.chair.mac, r = p.src, ci = inj.get(mac);
  const o = ci.apply(r.raw, p.u, r.fwi, r.rssi);
  const rec = { t_host: T_HOST0 + p.u, seq: p.seq, mac, rssi: o.rssi, noise_floor: r.noise_floor, channel: r.channel,
    ts_us: (TS0 + Math.round(p.u * 1e6)) % INJ.TS_WRAP, sig_len: r.sig_len, rx_state: r.rx_state, len: 128, fwi: r.fwi, raw: o.raw };
  csv.push(INJ.formatLine(rec.t_host, rec));
  const u = live.push(rec);
  if (u) byMac.get(mac).hops.push(u);
  const tr = ci.br.takeTruth(); const T = byMac.get(mac).truth; T.t.push(...tr.t); T.bpm.push(...tr.bpm);
}
const secs = (Date.now() - t0) / 1000;
check(secs < RUN_S / 4, `${RUN_S} s of a 5-chair room processed in ${secs.toFixed(1)} s (needs to run faster than real time several times over)`);

for (const c of byMac.values()) {
  let full = 0, shown = 0, ok = 0, mot = 0, rates = 0, urgentPause = [];
  for (const h of c.hops) {
    if (h.reliable) rates++;
    const w = INJ.windowTruth(c.truth, h.t, 30);
    if (w.full) { full++; if (h.reliable) { shown++; if (Math.abs(h.bpm - w.bpm) <= 2) ok++; } }
    if (h.motion) mot++;
    if (h.status === 'urgent' && /pause/i.test(h.reason)) urgentPause.push(h.t);
  }
  c.score = { hops: c.hops.length, full, shown, ok, mot, rates };
  console.log(`     ${c.seat} ${c.profile}: ${c.hops.length} updates, ${full} windows full of breathing, rate shown in ${shown}, within ±2/min ${ok}` +
    `, movement flagged in ${mot}, pause alerts ${episodes(urgentPause)}`);
  c.urgentPause = urgentPause;
}
const A1 = byMac.get('1a:00:00:00:01:01'), A2 = byMac.get('1a:00:00:00:01:02'), A3 = byMac.get('1a:00:00:00:01:03'), B1 = byMac.get('1a:00:00:00:01:04'), B2 = byMac.get('1a:00:00:00:01:05');
for (const c of [A1, A2, A3, B1]) check(c.score.shown > 0 && c.score.ok / c.score.shown >= 0.9, `${c.seat}: at least 90% of shown rates within ±2/min of the injected truth (${c.score.ok}/${c.score.shown})`);
// A2 replays sensor 2 from 40 s in, so its 18 s hold at 100 s lands on 140-158 s of the recording, a quiet stretch
const pauseAlert = A2.urgentPause.find((t) => t >= 100 && t <= 130);
check(pauseAlert !== undefined, `A2: the 18 s breath-hold from 100 s is flagged${pauseAlert !== undefined ? ' at ' + pauseAlert.toFixed(0) + ' s (' + (pauseAlert - 100).toFixed(0) + ' s after it began)' : ''}`);
check(!A2.urgentPause.some((t) => t >= 300 && t <= 330), 'A2: the 8 s breath-hold from 300 s is not flagged (adult minimum is 10 s)');
check(B1.hops.some((h) => h.motion && h.t >= 230 && h.t <= 240), 'B1: simulated movement at 230 s is detected as movement');
// an empty chair has no window full of breathing, so its rates are counted over every update
check(B2.score.rates <= 0.05 * B2.score.hops, `B2 (empty chair): no rate shown, or almost none (${B2.score.rates} of ${B2.score.hops} updates, at most 5%)`);
check(B2.hops.every((h) => h.status !== 'typical'), 'B2 (empty chair): never shows no breathing concern');
for (const st of ['urgent', 'watch']) console.log(`     B2 (empty chair) ${st}: ${episodes(B2.hops.filter((h) => h.status === st).map((h) => h.t))}`);
knownFailure(B2.urgentPause.length > 0, `B2 (empty chair): breathing-pause alerts ${episodes(B2.urgentPause)}`);

// ---- 4. files for the Python cross-check
fs.mkdirSync(outDir, { recursive: true });
// the first line marks the file as test data, as in the board's download; the pipelines read only CSI_DATA lines
const MARK = '# hinigram-injection-bench v1: simulated breathing added to real Wi-Fi packets; test data, not a patient recording; check_inject_bench.js';
fs.writeFileSync(path.join(outDir, 'bench_injected.csv'), [MARK, ...csv].join('\n') + '\n');
const log = { kind: 'hinigram-injection-log', version: 1, background: src.file, run_s: RUN_S, t_host0: T_HOST0,
  chairs: [...byMac.values()].map((c) => ({ seat: c.seat, mac: c.mac, profile: c.profile, depth: c.depth, empty: !!c.empty, script: c.script || null, moves: c.moves || [],
    truth: c.truth, js: c.hops.map((h) => ({ t: Math.round(h.t * 1000) / 1000, status: h.status, bpm: Number.isFinite(h.bpm) ? Math.round(h.bpm * 1000) / 1000 : null, reliable: !!h.reliable })) })) };
fs.writeFileSync(path.join(outDir, 'bench_truth.json'), JSON.stringify(log));
console.log(`     wrote ${path.join(outDir, 'bench_injected.csv')} (${csv.length} packets) and bench_truth.json`);
console.log((failures ? `${failures} check(s) failed` : 'all checks passed') + (known ? `; ${known} known open failure(s) reported above (KNOWN)` : ''));
process.exitCode = failures ? 1 : 0;
