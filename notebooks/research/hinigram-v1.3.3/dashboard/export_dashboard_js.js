// Build the dashboard's embedded data with the same code the page runs on a loaded CSV
// (hinigram_dsp.js + template_worker.js). Ground-truth curves for the demo come from the
// Python export (hinigram_live.breathing_waveform), which also serves as the parity reference.
const fs = require('fs'), vm = require('vm'), path = require('path');
const dir = __dirname;
const ctx = { console, Math, Date, Float64Array, Int16Array, Int32Array, Uint8Array, Array, Object, Number, String, Map, Set, JSON, Error, isFinite, parseInt, parseFloat, NaN, Infinity };
ctx.self = ctx; ctx.postMessage = () => {};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(dir, 'hinigram_dsp.js'), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(path.join(dir, 'template_worker.js'), 'utf8'), ctx);
const W = ctx.HinigramWorker;
const py = JSON.parse(fs.readFileSync(path.join(dir, 'dashboard_data.json'), 'utf8'));
const csv = { demo: path.join(dir, '..', 'semi', 'demo_semisynthetic.csv'), sample: path.join(dir, '..', 'demo_20261019_024431.csv') };
const out = { version: py.version, generated: py.generated, sources: {} };
for (const key of ['demo', 'sample']) {
  const ref = py.sources[key];
  const prof = {}; ref.sensors.forEach((s) => { prof[s.mac] = s.profile; });
  const d = W.analyzeText(fs.readFileSync(csv[key], 'utf8'), ref.file, prof);
  d.file = ref.file; d.title = ref.title; d.note = ref.note; delete d.short; delete d.bad;
  d.sensors.forEach((s, i) => {
    const r = ref.sensors[i];
    if (r.mac !== s.mac) throw new Error('sensor order mismatch');
    let diffs = 0;
    r.hops.status.forEach((st, k) => { if (st !== s.hops.status[k] || r.hops.reason[k] !== s.hops.reason[k] || r.hops.bpm[k] !== s.hops.bpm[k]) diffs++; });
    if (diffs) throw new Error(`${key} ${s.seat}: ${diffs} hops differ from the Python reference`);
    if (r.truth) s.truth = r.truth;
  });
  out.sources[key] = d;
}
const dst = path.join(dir, 'dashboard_data_final.json');
fs.writeFileSync(dst, JSON.stringify(out));
console.log('wrote', dst, fs.statSync(dst).size, 'bytes; hops identical to Python for every sensor');
