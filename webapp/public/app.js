'use strict';

// Renders the console from the server's state stream (/api/events, once a second). All analysis happens in the
// server; this file only draws what it is sent.

const STATUS = {
  urgent: 'Needs help now', watch: 'Watch', typical: 'No breathing concern',
  no_reading: 'No reliable reading', moving: 'Moving, reading paused', collecting: 'Collecting',
};
const TRACE_S = 60, QUALITY_S = 120, Y_RANGE = 3.5, FORMING_Q = 0.6;

const $ = (id) => document.getElementById(id);
const lanes = new Map(); // mac -> {el, q: query helper, status}
let lastRecOn = null;

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function bytes(n) {
  return n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1e3))} KB`;
}

function clock(s) {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
}

async function post(url, body) {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error((await res.json()).error || res.statusText);
  return res.json();
}

/** A canvas sized to its CSS box at the screen's pixel density, read fresh on every draw. */
function fit(canvas) {
  const dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return { ctx, w, h };
}

/** A signal ending at "now" on the right, on a 5 s grid: the raw live signal or the analysed breathing trace. */
function drawTrace(canvas, trace, fs, { spanS = TRACE_S, color = '--pen' } = {}) {
  const { ctx, w, h } = fit(canvas);
  const mid = h / 2, perS = w / spanS;
  ctx.lineWidth = 1;
  for (let s = 0; s <= spanS; s += 5) {
    ctx.strokeStyle = css(s % 10 === 0 ? '--rule-2' : '--rule');
    ctx.globalAlpha = s % 10 === 0 ? 0.6 : 0.5;
    const x = Math.round(w - s * perS) + 0.5;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  ctx.globalAlpha = 0.8;
  ctx.strokeStyle = css('--rule-2');
  ctx.beginPath(); ctx.moveTo(0, mid + 0.5); ctx.lineTo(w, mid + 0.5); ctx.stroke();
  ctx.globalAlpha = 1;
  if (trace.length) drawPen(ctx, trace, fs, w, mid, perS, color);
  // axis labels last, on a backing, so the trace never runs through them
  ctx.font = `11px ${css('--mono')}`;
  ctx.textBaseline = 'bottom';
  for (const [text, align, x] of [[`${spanS} s ago`, 'left', 2], ['now', 'right', w - 2]]) {
    const tw = ctx.measureText(text).width;
    ctx.fillStyle = css('--card');
    ctx.fillRect(align === 'left' ? x : x - tw - 4, h - 15, tw + 4, 15);
    ctx.fillStyle = css('--ink-2');
    ctx.textAlign = align;
    ctx.fillText(text, align === 'left' ? x + 2 : x - 2, h - 2);
  }
}

function drawPen(ctx, trace, fs, w, mid, perS, color) {
  const n = trace.length, x0 = w - (n - 1) * (perS / fs);
  const y = (v) => mid - (Math.max(-Y_RANGE, Math.min(Y_RANGE, v)) / Y_RANGE) * (mid - 6);
  ctx.strokeStyle = css(color);
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  let pen = false, lx = 0, ly = 0;
  trace.forEach((v, i) => {
    if (v === null) { pen = false; return; }
    lx = x0 + i * (perS / fs); ly = y(v);
    if (pen) ctx.lineTo(lx, ly); else ctx.moveTo(lx, ly);
    pen = true;
  });
  ctx.stroke();
  if (pen) {
    ctx.fillStyle = css(color);
    ctx.beginPath(); ctx.arc(lx, ly, 3.5, 0, 2 * Math.PI); ctx.fill();
  }
}

function drawQuality(canvas, quality) {
  const { ctx, w, h } = fit(canvas);
  const base = h - 1, slot = w / (QUALITY_S / 2);
  ctx.strokeStyle = css('--rule');
  ctx.beginPath(); ctx.moveTo(0, base + 0.5); ctx.lineTo(w, base + 0.5); ctx.stroke();
  if (quality.length) {
    const tEnd = quality[quality.length - 1].t;
    for (const p of quality) {
      const x = w - ((tEnd - p.t) / QUALITY_S) * w - slot;
      const bh = Math.max(2, p.q * (h - 4));
      ctx.fillStyle = css(p.motion ? '--watch' : p.reliable ? '--pen' : '--rule-2');
      ctx.fillRect(x + 1, base - bh, Math.max(1, slot - 2), bh);
    }
  }
  const ty = Math.round(base - FORMING_Q * (h - 4)) + 0.5;
  ctx.strokeStyle = css('--ink-2');
  ctx.setLineDash([3, 3]);
  ctx.beginPath(); ctx.moveTo(0, ty); ctx.lineTo(w, ty); ctx.stroke();
  ctx.setLineDash([]);
}

function laneFor(sensor, profiles) {
  let lane = lanes.get(sensor.mac);
  if (lane) return lane;
  const el = $('lane-tpl').content.firstElementChild.cloneNode(true);
  const q = (sel) => el.querySelector(sel);
  q('.lane-name').textContent = sensor.label;
  const select = q('.who-select');
  for (const [value, label] of Object.entries(profiles)) select.add(new Option(label, value));
  select.value = sensor.profile;
  select.addEventListener('change', () => post('/api/profile', { mac: sensor.mac, profile: select.value }).catch((e) => alertLane(lane, e.message)));
  lane = { el, q, status: null };
  lanes.set(sensor.mac, lane);
  $('lanes').append(el);
  return lane;
}

function alertLane(lane, msg) {
  lane.q('.next-title').textContent = msg;
}

function linkState(s) {
  const r = s.reading;
  if (s.lastPacketAgo > 3) return 'dead';
  if (r && (r.motion || r.status === 'moving')) return 'moving';
  if (r && r.reliable) return 'locked';
  if (r && r.quality >= FORMING_Q) return 'forming';
  return 'flow';
}

const HELD_S = 40;

/**
 * The rate beside a status, or null. Only a status the pipeline gave from a rate gets one: never "warming up",
 * "moving" or a breathing pause. The pipeline keeps such a status for a few seconds after a reading stops being
 * reliable; the rate it came from is then shown as held.
 */
function shownRate(r) {
  if (!r || !['typical', 'watch', 'urgent'].includes(r.status) || r.key.startsWith('pause')) return null;
  if (r.reliable && r.bpm !== null) return { bpm: Math.round(r.bpm), held: null };
  if (r.lastReliable && r.lastReliable.ago <= HELD_S) return { bpm: Math.round(r.lastReliable.bpm), held: r.lastReliable.ago };
  return null;
}

/** The ResoNet line: [value, note]. Never mixed into the reading above it. */
function modelLine(s, model) {
  const r = s.reading, m = s.model;
  if (!model || model.state !== 'ready') return ['–', model ? model.message : ''];
  if (!m) return ['–', 'first estimate after 30 s'];
  if (m.ago > 10) return ['–', 'no recent estimate'];
  if (r && (r.motion || r.status === 'moving')) return ['–', 'paused: movement'];
  if (m.rate === null || m.nShown === 0) return ['–', `not confident (0 of ${m.nModels} models) · second opinion, not used for alerts`];
  return [`${Math.round(m.rate)}/min`, `${m.nShown} of ${m.nModels} models agree · second opinion, not used for alerts`];
}

function renderLane(s, profiles, model) {
  const lane = laneFor(s, profiles), { el, q } = lane, r = s.reading;
  const status = r ? r.status : 'collecting';
  const rate = shownRate(r);
  el.dataset.stale = String(!!s.stale);
  q('.stale-note').hidden = !s.stale;
  q('.stale-note').textContent = s.stale ? `Not hearing ${s.label}: last packet ${ago(s.lastPacketAgo)} ago. Everything below is from then.` : '';
  el.dataset.status = status;
  el.dataset.reliable = String(rate !== null && rate.held === null);
  el.dataset.held = String(rate !== null && rate.held !== null);
  el.dataset.link = linkState(s);
  q('.rate-num').textContent = rate !== null ? String(rate.bpm) : '–';
  q('.rate-held').textContent = rate && rate.held !== null ? `last reliable reading, ${rate.held} s ago` : '';
  q('.status-text').textContent = STATUS[status] || status;
  q('.reason').textContent = r ? r.reason : `The first reading comes after 30 seconds (${Math.min(30, s.collectedS)} s so far).`;
  const [mValue, mNote] = modelLine(s, model);
  q('.model').dataset.shown = String(mValue !== '–');
  q('.model-value').textContent = mValue;
  q('.model-note').textContent = mNote;
  if (lane.status !== null && lane.status !== status) q('[aria-live]').textContent = `${s.label}: ${STATUS[status] || status}`;
  lane.status = status;
  if (document.activeElement !== q('.who-select')) q('.who-select').value = s.profile;

  const live = s.live;
  q('.live-empty').hidden = !!live;
  drawTrace(q('canvas.live'), live ? live.values : [], live ? live.fs : 10, { spanS: 30, color: '--ink-2' });
  q('canvas.live').setAttribute('aria-label', `${s.label} raw live signal, last 30 seconds${live ? `, subcarrier ${live.subcarrier}` : ''}.`);
  q('.trace-empty').hidden = s.trace.length > 0;
  q('.trace-empty').textContent = `The analysed breathing starts at 30 s (${Math.min(30, s.collectedS)} s so far).`;
  drawTrace(q('canvas.trace'), s.trace, s.traceFs);
  q('canvas.trace').setAttribute('aria-label', `${s.label} analysed breathing, last 60 seconds. ${STATUS[status] || status}.`);
  drawQuality(q('canvas.quality'), s.quality);
  const lastQ = s.quality.length ? s.quality[s.quality.length - 1].q : null;
  q('canvas.quality').setAttribute('aria-label', `${s.label} pattern strength over 2 minutes${lastQ === null ? '' : `, latest ${Math.round(lastQ * 100)} of 100`}.`);

  q('.next').dataset.level = s.guidance.level;
  q('.next-title').textContent = s.guidance.title;
  q('.next-detail').textContent = s.guidance.detail;

  q('.h-rate').textContent = `${s.packetsPerS}/s`;
  q('.h-rate').classList.toggle('weak', s.packetsPerS < 15);
  q('.h-rssi').textContent = s.rssi === null ? '–' : `${s.rssi} dBm`;
  q('.h-rssi').classList.toggle('weak', s.rssi !== null && s.rssi < -80);
  q('.h-loss').textContent = `${s.lossPct ?? 0}%`;
  q('.h-loss').classList.toggle('weak', s.lossPct > 20);
  q('.mac').title = `${s.lossSessionPct}% lost since this session started`;
  q('.h-steps').textContent = s.gainStepsPct === null ? '–' : `${s.gainStepsPct}%`;
  q('.mac').textContent = `${s.mac} · ${s.lossSessionPct}% lost this session`;
  q('.estimate').textContent = r && !r.reliable && r.raw !== null ? `unconfirmed estimate ${r.raw}/min` : '';
}

function renderTop(state) {
  const r = state.receiver || {}, el = $('link-state');
  const live = state.stream.linesPerS;
  let text = r.message || r.state;
  if (r.state === 'connected' && r.source === 'serial') text = `Receiver on ${r.path} · ${Number(r.baud).toLocaleString('en-US')} baud · ${live} lines/s`;
  else if (r.state === 'connected' && r.source === 'demo') text = `Simulated receiver · ${live} lines/s`;
  else if (r.state === 'connected' && r.source === 'replay') text = `Replaying ${r.path} · ${live} lines/s`;
  if (state.stream.dropped) text += ` · receiver dropped ${state.stream.dropped}`;
  el.dataset.state = r.state;
  $('link-text').textContent = text;
  $('sim-banner').hidden = r.source !== 'demo';

  const rec = state.recording;
  $('record').setAttribute('aria-pressed', String(rec.on));
  $('record-label').textContent = rec.on ? `Stop recording · ${clock(rec.seconds)} · ${bytes(rec.bytes)}` : 'Record';
  if (lastRecOn !== rec.on) loadRecordings();
  lastRecOn = rec.on;
}

function ago(s) {
  return s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
}

/** The chain that has to work, in order: receiver, data, transmitters, link, breathing. */
function renderStatus(state) {
  const r = state.receiver || {}, lps = state.stream.linesPerS;
  const byTx = Object.fromEntries(state.sensors.filter((s) => s.tx).map((s) => [s.tx, s]));
  const heard = state.sensors.filter((s) => !s.stale);
  const rxUp = r.state === 'connected';
  const checks = [];
  if (r.source === 'demo') checks.push(['ok', 'Simulated receiver', 'No hardware: the data is made up.']);
  else if (r.source === 'replay') checks.push(['ok', 'Replaying a recording', r.path]);
  else if (rxUp) checks.push(['ok', `Receiver on ${r.path}`, `${Number(r.baud).toLocaleString('en-US')} baud`]);
  else if (r.state === 'paused') checks.push(['warn', 'Receiver paused', 'A board is being identified or written.']);
  else checks.push(['bad', 'Receiver not connected', `${r.message || ''}. Plug the receiver board (CP2102, runs csi_rx) into this computer with a data cable.`]);
  if (!rxUp) checks.push(['off', 'Data from the receiver', 'Waits for the receiver.']);
  else if (lps >= 5) {
    const { logged, dropped } = state.stream; // only the bundle receiver reports both
    const inRx = logged !== null && dropped !== null ? `The receiver itself dropped ${dropped} of ${logged + dropped} lines (${((100 * dropped) / Math.max(1, logged + dropped)).toFixed(1)}%).` : '';
    checks.push([dropped > 0.05 * (logged || 0) ? 'warn' : 'ok', `Data arriving: ${lps} lines/s`, inRx]);
  }
  else checks.push(['bad', lps > 0 ? `Little data: ${lps} lines/s` : 'No data from the receiver', 'Check that the transmitters have power.']);
  // any number of transmitters: every one heard this session, now or before
  const txText = Object.keys(byTx).sort((a, b) => a - b).map((n) => {
    const s = byTx[n];
    return s.stale ? `TX${n} silent for ${ago(s.lastPacketAgo)}` : `TX${n} ${s.packetsPerS}/s`;
  }).join(' · ') || 'None yet. Power a transmitter on the same channel.';
  const silent = state.sensors.length - heard.length;
  checks.push([!rxUp ? 'off' : heard.length && !silent ? 'ok' : heard.length ? 'warn' : 'bad', `Hearing ${heard.length} transmitter${heard.length === 1 ? '' : 's'}${silent ? `, ${silent} gone quiet` : ''}`, txText]);
  if (rxUp && r.baud && heard.length) {
    const capacity = r.baud / 10, used = state.stream.bytesPerS / capacity; // 10 bits a byte on the wire
    const perTx = state.stream.bytesPerS / heard.length, room = Math.max(0, Math.floor((0.85 * capacity - state.stream.bytesPerS) / Math.max(perTx, 1)));
    checks.push([used > 0.85 ? 'bad' : used > 0.7 ? 'warn' : 'ok', `Serial link ${Math.round(used * 100)}% full`,
      used > 0.85 ? 'Full: lines are being lost. Use a faster serial speed, a lower packet rate or a second receiver.' : `Room for about ${room} more transmitter${room === 1 ? '' : 's'} at this rate.`]);
  }
  const weak = heard.filter((s) => s.lossPct > 20 || (s.rssi !== null && s.rssi < -80));
  checks.push([!heard.length ? 'off' : weak.length ? 'warn' : 'ok', weak.length ? 'Weak link' : 'Links clean',
    weak.map((s) => `${s.label}: ${s.lossPct}% lost, ${s.rssi} dBm`).join(' · ') || (heard.length ? 'Under 20% loss' : '')]);
  const reading = heard.filter((s) => shownRate(s.reading));
  checks.push([reading.length ? 'ok' : !heard.length ? 'off' : 'warn', reading.length ? 'Reading breathing' : 'No breathing pattern yet',
    reading.map((s) => `${s.label} ${shownRate(s.reading).bpm}/min`).join(' · ') || (heard.length ? 'Someone must sit still between a transmitter and the receiver.' : '')]);

  const firstBad = checks.find(([lvl]) => lvl === 'bad');
  const level = firstBad ? 'bad' : reading.length ? 'ok' : 'warn';
  const text = firstBad ? `Not working: ${firstBad[1].toLowerCase()}` : reading.length ? `Working: reading breathing on ${reading.map((s) => s.label).join(', ')}` : `Running: hearing ${heard.length} of 3 transmitters`;
  $('verdict').dataset.level = level;
  $('verdict-text').textContent = text;
  $('verdict-next').textContent = firstBad ? firstBad[2] : (checks.find(([lvl]) => lvl === 'warn') || [])[2] || '';
  $('checks').replaceChildren(...checks.map(([lvl, title, detail]) => {
    const li = document.createElement('li');
    li.dataset.level = lvl;
    li.innerHTML = '<span class="check-mark" aria-hidden="true"></span><span class="check-title"></span><span class="check-detail"></span>';
    li.querySelector('.check-title').textContent = title;
    li.querySelector('.check-detail').textContent = detail;
    return li;
  }));
}

function render(state) {
  renderTop(state);
  renderStatus(state);
  const seen = new Set();
  for (const s of state.sensors) {
    renderLane(s, state.profiles, state.model);
    seen.add(s.mac);
  }
  for (const [mac, lane] of lanes) if (!seen.has(mac)) { lane.el.remove(); lanes.delete(mac); }
  $('lanes-empty').hidden = state.sensors.length > 0;
}

async function loadRecordings() {
  const list = await fetch('/api/recordings').then((r) => r.json()).catch(() => []);
  const ul = $('rec-list');
  ul.replaceChildren(...list.slice(0, 12).map((f) => {
    const li = document.createElement('li');
    const name = document.createElement('span');
    name.className = 'rec-name';
    name.textContent = f.name;
    const meta = document.createElement('span');
    meta.className = 'rec-meta';
    meta.textContent = `${bytes(f.bytes)} · ${new Date(f.modified * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · `;
    const a = document.createElement('a');
    a.href = `/recordings/${encodeURIComponent(f.name)}`;
    a.download = f.name;
    a.textContent = 'Download';
    meta.append(a);
    li.append(name, meta);
    return li;
  }));
  $('rec-empty').hidden = list.length > 0;
}

$('record').addEventListener('click', async () => {
  const on = $('record').getAttribute('aria-pressed') === 'true';
  await post(on ? '/api/record/stop' : '/api/record/start').catch(() => {});
  loadRecordings();
});
$('reset').addEventListener('click', () => post('/api/reset').catch(() => {}));

let latest = null;
const events = new EventSource('/api/events');
events.addEventListener('state', (e) => {
  latest = JSON.parse(e.data);
  render(latest);
});
events.addEventListener('error', () => {
  const el = $('link-state');
  el.dataset.state = 'disconnected';
  $('link-text').textContent = 'The console server is not reachable. Start it again with npm start in webapp/.';
});
window.addEventListener('resize', () => latest && render(latest));
loadRecordings();
