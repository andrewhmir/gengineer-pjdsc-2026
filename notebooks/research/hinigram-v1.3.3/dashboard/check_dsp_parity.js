// The v1.3.3 board's JavaScript pipeline (hinigram_dsp.js) gives bit-for-bit the same output as the v1.3.2 one
// (history/hinigram_dsp_v132.js). v1.3.3 changed only how the Hampel filter finds its medians (about 3.7 times faster in this check)
// and lets the CSV parser accept tabs or semicolons. From the bundle folder:  node dashboard/check_dsp_parity.js
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const dir = __dirname, root = path.join(dir, '..');
const NEW = require(path.join(dir, 'hinigram_dsp.js'));
const OLD = require(path.join(root, 'history', 'hinigram_dsp_v132.js'));
const INJ = require(path.join(dir, 'hinigram_inject.js'));
const bits = (a, b) => { if (a.length !== b.length) return false; const A = new Uint8Array(Float64Array.from(a).buffer), B = new Uint8Array(Float64Array.from(b).buffer); return A.every((v, i) => v === B[i]); };
let fails = 0;
const ck = (ok, m) => { console.log((ok ? 'ok   ' : 'FAIL ') + m); if (!ok) fails++; };
const text = fs.readFileSync(path.join(root, 'demo_20261019_024431.csv'), 'utf8');
const S = OLD.parseText(text, 's');
for (const m of S.macs) { const a = OLD.linkFeatures(S.links[m], 10), b = NEW.linkFeatures(S.links[m], 10); ck(bits(a.X, b.X) && bits(a.activity, b.activity), `features identical on ${m} (${a.T} samples x ${a.Cn} channels)`); }
// ties, negative zeros, NaN and spikes: the cases where a different sort could pick a different median
const L = S.links[S.macs[0]];
const H = L.H.map((h, i) => { const re = Float64Array.from(h.re), im = Float64Array.from(h.im); if (i % 50 === 0) for (let s = 2; s < 64; s++) { re[s] = Math.round(re[s] / 8) * 8; im[s] = -0; } if (i % 333 === 0) re[10] = NaN; if (i % 97 === 0) re[20] *= 9; return { re, im }; });
ck(bits(OLD.linkFeatures(Object.assign({}, L, { H }), 10).X, NEW.linkFeatures(Object.assign({}, L, { H }), 10).X), 'features identical with ties, -0, NaN and spikes');
const ser = (R) => JSON.stringify(Object.entries(R.tracks || R).map(([k, v]) => [k, v && [Array.from(v.t), v.status, v.reason, Array.from(v.bpm, (x) => (Number.isNaN(x) ? 'nan' : x))]]));
ck(ser(OLD.analyzeSession(OLD.parseText(text, 's'), {})) === ser(NEW.analyzeSession(NEW.parseText(text, 's'), {})), 'whole-file analysis identical on the format sample');
const src = INJ.unpackBuffer(zlib.gunzipSync(Buffer.from(fs.readFileSync(path.join(dir, 'sample_packets.b64'), 'utf8'), 'base64')));
const run = (D) => { const pl = new INJ.Player(src, src.macs.map((m, i) => ({ mac: '1a:00:00:00:02:0' + (i + 1), src: m, offset: i * 30 })), null);
  const inj = src.macs.map((m, i) => new INJ.ChairInjector(50 + i, { bpm: [12, 20, 30][i], depth: [0.05, 0.03, 0.015][i] })); const ls = new D.LiveSession({}); const out = [];
  for (const p of pl.until(200)) { const i = +p.chair.mac.slice(-1) - 1, o = inj[i].apply(p.src.raw, p.u, p.src.fwi, p.src.rssi);
    const u = ls.push({ seq: p.seq, mac: p.chair.mac, rssi: o.rssi, noise_floor: -96, channel: 6, ts_us: 100000000 + Math.round(p.u * 1e6), sig_len: 47, rx_state: 1, len: 128, fwi: p.src.fwi, raw: o.raw });
    if (u) out.push([u.mac, u.t, u.status, u.reason, u.bpm, u.raw, u.quality, u.pause, u.snr, u.wave]); }
  return JSON.stringify(out); };
let t = Date.now(); const a = run(OLD), tOld = (Date.now() - t) / 1000; t = Date.now(); const b = run(NEW), tNew = (Date.now() - t) / 1000;
ck(a === b, `live pipeline identical on 200 s of a 3-chair stream (v1.3.2 ${tOld.toFixed(1)} s, v1.3.3 ${tNew.toFixed(1)} s: ${(tOld / tNew).toFixed(1)}x faster)`);
const row = OLD.parseLine(text.split('\n')[0]), tsv = text.split('\n')[0].replace(/,(?=[^\]]*\[)|,(?![^\[]*\])/g, '\t');
const r2 = NEW.parseLine(tsv);
ck(row && r2 && r2.seq === row.seq && r2.mac === row.mac && r2.raw.every((v, i) => v === row.raw[i]), 'a tab-separated line parses to the same packet');
console.log(fails ? fails + ' check(s) failed' : 'all checks passed');
process.exitCode = fails ? 1 : 0;
