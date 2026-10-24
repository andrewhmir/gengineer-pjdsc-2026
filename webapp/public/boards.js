'use strict';

// The Boards panel: every ESP32 on USB, what it runs, and a role, transmitter ID and firmware version to write to it.
// The server identifies, flashes and sets IDs; this file draws the list, asks before overwriting, and follows the
// job in the state stream.

const choice = new Map(); // port -> {role, id} picked in its row
const confirming = new Set(); // ports showing "this replaces ..."
let boardsView = null; // last GET /api/boards
let lastJobPhase = null;
let pollTimer = null;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function button(text, cls, onClick, disabled = false) {
  const b = el('button', `btn ${cls || ''}`.trim(), text);
  b.type = 'button';
  b.disabled = disabled;
  b.addEventListener('click', onClick);
  return b;
}

const roleText = (role, id) => (role === 'rx' ? 'Receiver' : `Transmitter ${id}`);
const shortText = (role, id) => (role === 'rx' ? 'RX' : `TX${id}`);
const SET_NAMES = { team: 'team', bundle: 'v1.3.3 bundle', universal: 'universal', hinigram: 'v1.3.3 / universal' };

function chosenVersion() {
  const v = boardsView.versions.find((x) => x.key === $('boards-set').value);
  return v || boardsView.versions[0] || null;
}

function runsText(b) {
  const id = b.identity;
  if (!id) return b.liveReceiver ? 'Receiver: sending CSI_DATA to this console now' : 'Not identified yet';
  if (!id.booted && !id.project && !id.csi) return 'Did not answer. Check the data cable, or press its EN button once and identify again.';
  const what = id.project ? `runs ${id.project}${id.version ? ` v${id.version}` : ''}` : 'runs firmware that does not say its name';
  const set = id.set ? `, ${SET_NAMES[id.set]} firmware` : '';
  const stored = id.set === 'universal' ? (id.idStored ? ', ID stored on the board' : ', no ID stored yet') : '';
  return `${id.role ? roleText(id.role, id.id) : 'Not a Hinigram role'}: ${what}${set}${stored}${id.idf ? ` (ESP-IDF ${id.idf})` : ''}`;
}

function macText(b) {
  const id = b.identity, parts = [];
  if (id && id.chipMac) parts.push(`chip ${id.chipMac}`);
  if (id && id.sendsAs) parts.push(`sends as ${id.sendsAs}`);
  if (b.teamLabel) parts.push(`the team set this board up as ${b.teamLabel}`);
  return parts.join(' · ');
}

function warnings(view) {
  const out = [], seen = {};
  for (const b of view.boards) {
    const id = b.identity;
    const k = id && id.role ? shortText(id.role, id.id) : b.liveReceiver ? 'RX' : null;
    if (k) seen[k] = (seen[k] || 0) + 1;
  }
  for (const [k, n] of Object.entries(seen)) {
    if (n > 1) out.push(`${n} boards are ${k}. ${k === 'RX' ? 'Use one receiver.' : 'They send from the same address, so the receiver cannot tell them apart. Give one a new ID.'}`);
  }
  return out;
}

function renderBoards() {
  const view = boardsView;
  if (!view) return;
  const job = view.job, running = job && !['done', 'failed'].includes(job.phase);
  const setSelect = $('boards-set');
  const keep = setSelect.value;
  setSelect.replaceChildren(...view.versions.map((v) => new Option(`${view.sets[v.set].label} · ${v.version} · built ${new Date(v.builtAt).toLocaleDateString()}`, v.key)));
  if (view.versions.some((v) => v.key === keep)) setSelect.value = keep;
  const version = chosenVersion(), set = version ? view.sets[version.set] : null;
  $('boards-images').textContent = version
    ? `${view.versions.length} firmware version${view.versions.length > 1 ? 's' : ''} in the library. ${set.ids ? `This one has transmitters ${set.ids.join(', ')} only.` : 'This one gives transmitters any ID from 1 to 254; the next free one is filled in.'}`
    : 'The firmware library is empty, so boards can be identified but not written. In webapp/, run: node tools/build-firmware.js';
  const warn = warnings(view);
  $('boards-warn').hidden = !warn.length;
  $('boards-warn').textContent = warn.join(' ');
  $('board-empty').hidden = view.boards.length > 0;
  $('boards-identify-all').disabled = !!running || !view.boards.length;

  $('board-list').replaceChildren(...view.boards.map((b) => {
    const li = el('li', 'board'), cur = b.identity || {};
    if (cur.role || b.liveReceiver) li.dataset.role = cur.role || 'rx';
    const info = el('div', 'board-id');
    const port = el('p', 'board-port');
    port.append(el('strong', null, b.path), ` · ${b.chip} `);
    if (cur.role) port.append(el('span', 'board-role', shortText(cur.role, cur.id)), ' ');
    if (b.liveReceiver) port.append(el('span', 'badge', 'live receiver'));
    info.append(port, el('p', 'board-runs', runsText(b)), el('p', 'board-mac', macText(b)));

    const pick = choice.get(b.path) || { role: cur.role || 'tx', id: cur.role === 'tx' && cur.id ? cur.id : view.nextId || 1 };
    const act = el('div', 'board-act');
    const roleSel = el('select');
    roleSel.add(new Option('Receiver', 'rx'));
    roleSel.add(new Option('Transmitter', 'tx'));
    roleSel.value = pick.role;
    const idBox = el('input');
    Object.assign(idBox, { type: 'number', min: 1, max: set && set.ids ? Math.max(...set.ids) : 254, value: pick.id, title: 'Transmitter ID' });
    idBox.hidden = pick.role !== 'tx';
    const update = () => {
      choice.set(b.path, { role: roleSel.value, id: Number(idBox.value) || 1 });
      confirming.delete(b.path);
      renderBoards();
    };
    roleSel.addEventListener('change', update);
    idBox.addEventListener('change', update);
    const lab = el('label', null, 'Make this ');
    lab.append(roleSel, idBox);
    act.append(
      lab,
      button('Flash', 'btn-primary', () => { confirming.add(b.path); renderBoards(); }, !!running || !version),
      button('Identify', '', () => identifyBoard(b.path), !!running),
    );
    if (cur.set === 'universal' && pick.role === 'tx' && pick.id !== cur.id) {
      act.append(button(`Change ID to ${pick.id}`, '', () => setBoardId(b.path, pick.id), !!running));
    }
    li.append(info, act);

    if (confirming.has(b.path) && !running && version) {
      const box = el('div', 'board-confirm');
      const project = pick.role === 'rx' ? set.rx : set.tx.replace('<ID>', pick.id);
      const target = `${project} ${version.version} (${roleText(pick.role, pick.id)})`;
      const now = cur.project || cur.runs;
      const tooHigh = pick.role === 'tx' && set.ids && !set.ids.includes(pick.id);
      box.append(el('p', null, tooHigh
        ? `This firmware has transmitters ${set.ids.join(', ')} only. Choose one of those, or a universal firmware version for ID ${pick.id}.`
        : now ? `This replaces ${now} on ${b.path} with ${target}.` : `This replaces whatever is on ${b.path} with ${target}. Press Identify first to see what that is.`));
      const btns = el('div');
      if (!tooHigh) btns.append(button('Write firmware', 'btn-primary', () => flashBoard(b.path, pick, version.key)));
      btns.append(button('Cancel', '', () => { confirming.delete(b.path); renderBoards(); }));
      box.append(btns);
      li.append(box);
    }
    if (job && job.port === b.path) li.append(jobBox(job));
    return li;
  }));
}

function jobBox(job) {
  const box = el('div', 'board-job');
  box.dataset.phase = job.phase;
  const title = { starting: 'Starting', connecting: 'Connecting to the board', writing: `Writing ${job.label}`, verified: 'Checking what was written', checking: 'Restarting the board', done: 'Done', failed: 'Not written' }[job.phase] || job.phase;
  box.append(el('p', null, `${title}${job.phase === 'writing' ? ` · ${job.pct || 0}%` : ''}`));
  if (!['done', 'failed'].includes(job.phase)) {
    const bar = el('progress');
    bar.max = 100;
    bar.value = job.phase === 'writing' ? job.pct || 0 : job.phase === 'checking' || job.phase === 'verified' ? 100 : 0;
    box.append(bar);
  }
  if (job.needBoot && job.phase === 'connecting') box.append(el('p', 'job-boot', 'Hold the BOOT button on this board now, until writing starts (2 to 5 seconds). Do not press EN.'));
  if (job.phase === 'writing') box.append(el('p', null, 'Let go of BOOT, and do not touch the board or its cable until this finishes.'));
  if (job.message && job.phase !== 'writing') box.append(el('p', null, job.message));
  return box;
}

function showProblem(text) {
  $('boards-warn').hidden = false;
  $('boards-warn').textContent = text;
}

async function loadBoards() {
  try {
    boardsView = await (await fetch('/api/boards')).json();
  } catch {
    return;
  }
  if (!document.querySelector('#boards select:focus, #boards input:focus')) renderBoards();
}

async function identifyBoard(port) {
  confirming.delete(port);
  const li = [...document.querySelectorAll('.board')].find((x) => x.querySelector('.board-port strong').textContent === port);
  if (li) li.querySelector('.board-runs').textContent = 'Restarting it and reading what it prints…';
  await post('/api/boards/identify', { path: port }).catch((e) => showProblem(`${port}: ${e.message}`));
  await loadBoards();
}

async function setBoardId(port, id) {
  const li = [...document.querySelectorAll('.board')].find((x) => x.querySelector('.board-port strong').textContent === port);
  if (li) li.querySelector('.board-runs').textContent = `Giving it ID ${id}…`;
  await post('/api/boards/set-id', { path: port, id }).catch((e) => showProblem(`${port}: ${e.message}`));
  choice.delete(port);
  await loadBoards();
}

async function flashBoard(port, pick, version) {
  confirming.delete(port);
  const failed = await post('/api/boards/flash', { path: port, role: pick.role, id: pick.id, version }).then(() => null, (e) => e.message);
  choice.delete(port);
  await loadBoards();
  if (failed) showProblem(`${port} was not written: ${failed}`);
}

$('boards-set').addEventListener('change', () => {
  confirming.clear();
  renderBoards();
});

$('boards-identify-all').addEventListener('click', async () => {
  for (const b of (boardsView && boardsView.boards) || []) await identifyBoard(b.path);
});

$('boards-toggle').addEventListener('click', toggleBoards);
if (location.hash === '#boards') toggleBoards();

function toggleBoards() {
  const open = $('boards').hidden;
  $('boards').hidden = !open;
  $('boards-toggle').setAttribute('aria-expanded', String(open));
  clearInterval(pollTimer);
  if (open) {
    loadBoards();
    pollTimer = setInterval(loadBoards, 4000);
  }
}

events.addEventListener('state', (e) => {
  const job = JSON.parse(e.data).boardJob;
  if (!job || !boardsView) return;
  boardsView.job = job;
  if (!$('boards').hidden && !document.querySelector('#boards select:focus, #boards input:focus')) renderBoards();
  if (job.phase !== lastJobPhase && ['done', 'failed'].includes(job.phase)) loadBoards();
  lastJobPhase = job.phase;
});
