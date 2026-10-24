'use strict';

// Builds the firmware library the console's Boards panel writes from. Each firmware set is built at its current
// version into webapp/.firmware/library/<set>/<version>/, and every version built before is kept, so any of them can
// still be written to a board. A version is the git commit of the set's folders (with "-dirty.<hash>" for changes
// not yet committed), plus the firmware's own version.txt when it has one; the bundle's is its folder's name.
//
//   team       the team's csi_rx and csi_tx1..3 (csi_rx gets the two settings in csi_rx.sdkconfig.defaults)
//   bundle     the v1.3.3 bundle's hinigram_receiver, and hinigram_node built as nodes 1, 2 and 3
//   universal  hinigram_receiver and hinigram_universal_node, one transmitter image for any number of boards
//
// Builds happen in webapp/.firmware/, outside the source folders, which stay untouched. Needs ESP-IDF 5.x.
//
//   node tools/build-firmware.js [--set NAME] [--firmware DIR] [--bundle DIR] [--force] [--idf-init "COMMAND"]

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { parseArgs } = require('node:util');
const { SETS, CACHE, LIBRARY, imageKey, findFirmwareDir, findEsptool, readLibrary } = require('../src/boards');
const { DEFAULT_BUNDLE } = require('../src/model');

function windowsIdfInit() {
  const json = 'C:\\Espressif\\esp_idf.json';
  if (!fs.existsSync(json)) return null;
  const id = Object.keys(JSON.parse(fs.readFileSync(json, 'utf8')).idfInstalled || {})[0];
  return id ? `C:\\Espressif\\idf_cmd_init.bat ${id} >nul 2>&1` : null;
}

function run(init, cmd, cwd) {
  const full = `${init} && ${cmd}`;
  // ESP-IDF's export.bat refuses to run when MSYSTEM is set at all, which Git Bash does
  const env = { ...process.env };
  delete env.MSYSTEM;
  const opts = { cwd, stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 64 * 1024 * 1024, env };
  try {
    return process.platform === 'win32' ? execFileSync('cmd', ['/d', '/s', '/c', full], opts).toString() : execFileSync('bash', ['-c', full], opts).toString();
  } catch (e) {
    const out = `${e.stdout || ''}${e.stderr || ''}`.trim().split(/\r?\n/).slice(-15).join('\n');
    throw new Error(`${cmd}\nfailed in ${cwd}:\n${out}`);
  }
}

const git = (dir, ...args) => execFileSync('git', ['-C', dir, ...args], { stdio: 'pipe' }).toString().trim();

/** The source files of a project, without build output, in a stable order. */
function sourceFiles(dir) {
  const out = [];
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      if (['build', 'managed_components'].includes(e.name) || /^sdkconfig(\.old)?$/.test(e.name) || e.name === 'dependencies.lock') continue;
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else out.push(p);
    }
  };
  walk(dir);
  return out;
}

/** The version of a set's source: its git commit, marked dirty with a content hash when it has uncommitted changes. */
function versionOf(set, dir, projects) {
  const hash = crypto.createHash('sha256');
  for (const p of projects) for (const f of sourceFiles(path.join(dir, p))) hash.update(path.relative(dir, f)).update(fs.readFileSync(f));
  const content = hash.digest('hex').slice(0, 8);
  // the bundle is an unzipped folder, not under version control: named by its folder, its content hash shows edits
  if (set === 'bundle') return { version: `${path.basename(path.dirname(dir)).replace(/^Hinigram_/, '')}+${content}`, commit: null, content };
  const own = projects.map((p) => path.join(dir, p, 'version.txt')).filter((f) => fs.existsSync(f)).map((f) => fs.readFileSync(f, 'utf8').trim())[0];
  const commit = git(dir, 'log', '-1', '--format=%h', '--', ...projects);
  // the component manager rewrites dependencies.lock for each IDF version; that is not a change to the firmware
  const dirty = git(dir, 'status', '--porcelain', '--', ...projects, ':(exclude,glob)**/dependencies.lock') !== '';
  const rev = commit ? `${commit}${dirty ? `-dirty.${content}` : ''}` : `uncommitted.${content}`;
  return { version: own ? `${own}+${rev}` : rev, commit: rev, content };
}

/** The roles a set builds: the receiver, then one image per fixed ID or a single universal transmitter image. */
function rolesOf(set) {
  const s = SETS[set];
  return [['rx', null, s.rx], ...(s.ids ? s.ids.map((id) => ['tx', id, s.tx(id)]) : [['tx', null, s.tx()]])];
}

/** The sdkconfig defaults files for one build: the project's own file, then the extra settings that build needs. */
function defaultsFor(set, role, id, proj) {
  const files = [];
  if (fs.existsSync(path.join(proj, 'sdkconfig.defaults'))) files.push(path.join(proj, 'sdkconfig.defaults'));
  if (set === 'team' && role === 'rx') files.push(path.join(__dirname, 'csi_rx.sdkconfig.defaults'));
  if (set === 'bundle' && role === 'tx') {
    const f = path.join(CACHE, `defaults-bundle-tx${id}`);
    fs.writeFileSync(f, `CONFIG_HINIGRAM_NODE_ID=${id}\n`); // hinigram_node takes its ID at build time
    files.push(f);
  }
  return files;
}

function main() {
  const { values } = parseArgs({ options: { set: { type: 'string' }, firmware: { type: 'string' }, bundle: { type: 'string' }, force: { type: 'boolean', default: false }, 'idf-init': { type: 'string' } } });
  const teamDir = values.firmware ? path.resolve(values.firmware) : findFirmwareDir();
  const sources = { team: teamDir, universal: teamDir, bundle: path.join(values.bundle ? path.resolve(values.bundle) : DEFAULT_BUNDLE, 'firmware') };
  const init = values['idf-init'] || (process.platform === 'win32' ? windowsIdfInit() : '. "$IDF_PATH/export.sh" >/dev/null');
  if (!init) throw new Error('ESP-IDF not found. Install ESP-IDF 5.x or pass --idf-init.');
  const esptool = findEsptool();
  if (!esptool) throw new Error('esptool was not found (it comes with ESP-IDF).');
  fs.mkdirSync(LIBRARY, { recursive: true });
  const idfVersion = run(init, 'idf.py --version', CACHE).trim().split(/\r?\n/).pop();
  const library = readLibrary();

  for (const set of values.set ? [values.set] : Object.keys(SETS)) {
    const src = sources[set];
    const roles = rolesOf(set);
    const projects = [...new Set(roles.map(([, , p]) => p))];
    if (!src || !projects.every((p) => fs.existsSync(path.join(src, p)))) {
      console.log(`[${set}] skipped: ${projects.join(', ')} not found${src ? ` in ${src}` : ''}`);
      continue;
    }
    const { version, commit } = versionOf(set, src, projects);
    const key = `${set}@${version}`;
    if (!values.force && library.some((e) => e.key === key)) {
      console.log(`[${set}] ${version} is already in the library`);
      continue;
    }
    const outDir = path.join(LIBRARY, set, version);
    fs.mkdirSync(outDir, { recursive: true });
    const images = {};
    for (const [role, id, project] of roles) {
      const proj = path.join(src, project), tag = `${set}-${imageKey(set, role, id)}`;
      const build = path.join(CACHE, 'build', tag), cfg = path.join(CACHE, 'build', `sdkconfig-${tag}`);
      const defs = defaultsFor(set, role, id, proj);
      const base = `idf.py -C "${proj}" -B "${build}" -D "SDKCONFIG=${cfg}"${defs.length ? ` -D "SDKCONFIG_DEFAULTS=${defs.join(';')}"` : ''}`;
      console.log(`[${set} ${version}] ${role}${id ? ` ${id}` : ''}: building ${project}`);
      // the component manager rewrites the project's dependencies.lock; put it back so the source stays untouched
      const lock = path.join(proj, 'dependencies.lock');
      const lockBefore = fs.existsSync(lock) ? fs.readFileSync(lock) : null;
      try {
        if (!fs.existsSync(cfg)) run(init, `${base} set-target esp32`, proj);
        run(init, `${base} build`, proj);
      } finally {
        if (lockBefore) fs.writeFileSync(lock, lockBefore);
        else if (fs.existsSync(lock)) fs.rmSync(lock);
      }
      const file = path.join(set, version, `${imageKey(set, role, id)}.bin`);
      // ESP-IDF's own Python, named in full: a bare "python" can resolve to one without esptool
      execFileSync(esptool.python, ['-m', 'esptool', '--chip', 'esp32', 'merge_bin', '-o', path.join(LIBRARY, file), '@flash_args'], { cwd: build, stdio: 'pipe' });
      const bytes = fs.readFileSync(path.join(LIBRARY, file));
      images[imageKey(set, role, id)] = { project, file: file.split(path.sep).join('/'), bytes: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
    }
    const entry = { key, set, version, builtAt: new Date().toISOString(), idfVersion, source: { dir: src, commit }, images };
    fs.writeFileSync(path.join(outDir, 'info.json'), `${JSON.stringify(entry, null, 2)}\n`);
    const kept = readLibrary().filter((e) => e.key !== key);
    fs.writeFileSync(path.join(LIBRARY, 'index.json'), `${JSON.stringify([entry, ...kept], null, 2)}\n`);
    console.log(`[${set}] ${version} added to the library (${Object.keys(images).join(', ')})`);
  }
}

main();
