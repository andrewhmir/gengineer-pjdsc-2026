# Hinigram Kiosk Station Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved self-service screening-station design into a working web application whose patient face matches `final-kiosk.html` and whose backend really measures: Start → 3 s settle → 30 s capture → one of `regular` / `irregular` / `unclear`.

**Architecture:** One uvicorn process. A source (simulator, replay fixture, or serial Rx) pushes 100 Hz frames into a time-indexed ring buffer; a session state machine owns `idle → settle → measuring → result`; a pure-numpy/scipy pipeline (Hampel → unwrap → PCA → best-Tx → 0.2–0.5 Hz Butterworth → peak RR, plus a driven Hopf oscillator and PLV) produces the outcome; the browser polls one JSON endpoint at 4 Hz and renders server-supplied copy, while a canvas module draws the station scene. No Node, no build step, no persistence.

**Tech Stack:** Python 3.12, FastAPI + Jinja2, uvicorn, pydantic v2 + pydantic-settings, numpy, scipy, pyserial (optional serial path), vanilla JS + canvas. Tests: pytest, httpx TestClient.

**Spec:** [`specs/2026-10-17-webapp-design.md`](2026-10-17-webapp-design.md) — this plan implements its **kiosk slice** only. §1.3, §7, §8.1, §10.1, §11, §12 are the load-bearing sections; §9, §10.2–10.5 (staff graph, sessions, torus, method page) are deferred by maintainer decision on 2026-10-17 and are listed under *Deferred* below.

## Global Constraints

Every task's requirements implicitly include this section. Values are copied from the spec; do not restate them differently in code comments.

- Serve `http://127.0.0.1:8765`. Any other `--host` prints a warning. No authentication (single-operator, local).
- One command from a clean clone: `cd webapp && uv sync && uv run hinigram`. No Node, no build step, no network at run time.
- Timing: settle 3 s, capture 30 s, evaluation < 400 ms, result auto-reset 20 s.
- Detector: Hampel window 7 / 3 MAD → unwrap per subcarrier → first principal component per Tx → best Tx by in-band SNR → Butterworth 0.2–0.5 Hz, 4th order, `sosfiltfilt` → dominant peak with parabolic interpolation. Hopf `dz/dt = (μ + iω)z − |z|²z + g·x(t)` with μ = −0.5, ω = 2π·0.25, g = 1.0, RK4 at frame rate, `x` normalised to unit RMS. `PLV = |mean_t exp(i(φ_breath − φ_osc))|`.
- Thresholds: RR band 0.2–0.5 Hz; tachypnea = RR > 24 **and** PLV < 0.60; unsteady = PLV < 0.40 with RR in band; regular = 8 ≤ RR ≤ 20 **and** PLV ≥ 0.60; watch = 20 < RR ≤ 24 **or** 0.40 ≤ PLV < 0.60 (still `regular`, advice `watch`); apnea = no breath phase ≥ 10 s; min 3 breaths; motion = > 2 s of band power above 3 Hz.
- Exactly three outcomes — `regular`, `irregular`, `unclear` — each with patient copy. Low or absent confidence forces `unclear`, never a clinical outcome.
- Nothing is measured before an explicit Start. No identifiers, no camera, no audio, no images, no persisted rows. Session ids are `s-` + 6 random hex, unrelated to the person.
- Patient-facing text ≥ 16 px, primary actions ≥ 56 px tall, status double-encoded (dot **and** word), focus visible at 2 px accent outline, motion stops under `prefers-reduced-motion`.
- Tokens live in one place, `hinigram/static/css/app.css`: `#eef1f5` surface, `#ffffff` card, `#0e1a28` / `#5b6b7d` / `#8697a9` ink, `#dfe6ee` line, `#0d6e78` accent, `#0f7b4f` / `#8f5600` / `#b3261e` ok/warn/crit. No template or stylesheet references an external host.
- Offline, deterministic tests; the webapp suite runs in under 15 s with no hardware. Clocks are injected — no `time.time()` inside pure functions under test.
- The root suite (`uv run pytest` at the repository root) must still pass, and root `ruff format --check .` covers `webapp/` too, so webapp code uses the same 100-column, Python 3.12 style.

### Execution notes (this machine)

- Set the cache directory before any `uv` command, or uv fails on its out-of-workspace cache: `$env:UV_CACHE_DIR = "C:\Users\Andrew\Desktop\Gengineer\gengineer-pjdsc-2026\.uvcache"`.
- `bash` does not work under this sandbox. Use PowerShell for every command.
- Visual verification uses Chrome headless (installed) rather than a Node toolchain:
  `& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu --window-size=1280,720 --screenshot="C:\Users\Andrew\Desktop\Gengineer\.superpowers\shots\kiosk-idle.png" http://127.0.0.1:8765/`
  Write screenshots outside the repository (`.superpowers/` is gitignored).
- Reference mockup: `C:\Users\Andrew\Desktop\Gengineer\.superpowers\mockups\final-kiosk.html` and its screenshots `shot-kiosk-idle.png`, `shot-kiosk-measuring.png`, `shot-kiosk-result.png`. It is **not** in the repository and must not be committed.

## Review Focus

The six failure modes most likely to reach a person at the station. Each line gets a test in the task that owns the code.

1. **Refresh or a second tab mid-session.** Reloading the page must rejoin the running session from `GET /api/v1/session` — same id, same countdown — and must never create a second session or reset the capture.
2. **Double Start / double Stop / Done during measuring.** One press, one transition. A second press while busy is a 409 and the page keeps rendering the server's truth on the next poll.
3. **The previous person's result left on screen.** After 20 s, or on Done, the result and the id are gone; the next Start gets a fresh id and empty buffers, and the scene drops back to the dashed mark.
4. **An empty zone, or someone stepping away during capture.** Settle finds no respiratory signal and returns to idle rather than measuring noise; a motion burst or a pause in breathing produces `unclear` or `apnea`, never a confident `regular`.
5. **Clocks and timezones.** The countdown comes from the server's `elapsed_ms` / `duration_ms`, so a browser clock minutes out of sync cannot show `0 seconds` while measuring, and a laptop resuming from sleep produces `unclear`, not a result computed from a stale window.
6. **The scene at other viewports.** 1280×720, 1024×768, and a narrow phone width: the mark and figure stay visible, the panel's primary action stays reachable, and resizing mid-measure does not blank the canvas.

---

## File Structure

```
webapp/
  pyproject.toml                     own manifest; console script `hinigram`
  uv.lock                            locked
  README.md                          dated framework decision, quickstart, scenario table
  AGENTS.md                          lane rules now that the framework is chosen
  hinigram/
    __init__.py                      __version__
    config.py                        Settings (HINIGRAM_* env) + thresholds()
    contracts.py                     pydantic models: Frame, SessionState, Result, Trace, Health
    cli.py                           argparse → Settings → uvicorn, banner, host warning
    sources.py                       Source protocol; Simulator, Replay, Serial; simulate_frames()
    station.py                       session state machine; owns clock, ids, evaluation trigger
    app.py                           app factory, lifespan, routes, polling endpoint
    pipeline/
      __init__.py
      frames.py                      Frame parsing, per-Tx ring buffers, Window
      dsp.py                         Hampel, PCA, bandpass, SNR, RR, motion, flat, decimate
      hopf.py                        oscillator, Hilbert phase, PLV, winding
      analyze.py                     one window → Analysis (orchestrates dsp + hopf)
      rules.py                       outcome rules, patient copy, stage/chip/step copy
    templates/
      base.html                      head, tokens, script tags
      kiosk.html                     station page: header, stage card, panel, disclaimer
    static/
      css/app.css                    design tokens + components (the only place colours live)
      js/station.js                  canvas scene: projection, masts, figure, rings, tag
      js/wave.js                     rhythm strip for the staff-details fold
      js/app.js                      polling client, panel renderer, button wiring, clock
    fixtures/
      scenarios.json                 named demo scenarios and their parameters
      replay_session.jsonl.gz        committed synthetic 33 s session (gzipped: ~150 KB)
  tests/
    conftest.py                      FakeClock, settings factory, frame injection, TestClient,
                                     and the signal helpers (`synth`, `fake_window`,
                                     `fake_series`, `analysis`, `analyse_scenario`) — each
                                     added by the first task whose tests use it
    test_frames.py                   parsing, ring buffers, window selection
    test_dsp.py                      RR accuracy, Hampel, bandpass, SNR, motion, flat, PCA
    test_hopf.py                     PLV bounds, jitter sensitivity, winding
    test_analyze.py                  per-scenario analysis values, Tx choice
    test_rules.py                   every rule row, boundary, copy, confidence
    test_sources.py                 simulator determinism, replay fixture, serial parser
    test_station.py                 transitions, reset, ids, no capture before Start
    test_api.py                     routes, status codes, end-to-end scenario through HTTP
    test_templates.py               no external hosts, disclaimer, caption, no PLV in HTML
    test_accessibility.py           16 px floor, 56 px actions, focus style, double encoding
```

Root files touched: `pyproject.toml` (workspace exclusion), `README.md` (map + quickstart),
`AGENTS.md` (lane map + reminder), `docs/ARCHITECTURE.md`, `docs/README.md`, `.env.example`,
`.github/workflows/ci.yml`, `CHANGELOG.md`, `tests/test_placeholders.py`,
`tests/test_agent_instructions.py`.

**Deferred (spec §5 modules absent from this build, and why):** `store.py` (nothing is
persisted in the kiosk build), `topology/*` and the `/staff` routes (deferred by maintainer),
`templates/kiosk_result.html` (the panel is rendered client-side from the session payload, so
patient copy ships in JSON and is still tested in Python), `torus.js` / `rose.js` / `system.js`
(deferred with the staff surfaces). `sources.py` keeps the serial adapter because the station
must be able to read real hardware later; it is exercised with a fake stream.

---

### Task 1: Lane scaffold, manifest, first route, and the repository's own record

**Files:**
- Create: `webapp/pyproject.toml`, `webapp/uv.lock`, `webapp/hinigram/__init__.py`, `webapp/hinigram/config.py`, `webapp/hinigram/contracts.py` (this task adds `Thresholds` and `Health` only; later tasks extend it), `webapp/hinigram/app.py`, `webapp/hinigram/cli.py`, `webapp/hinigram/templates/base.html`, `webapp/hinigram/templates/kiosk.html`, `webapp/hinigram/static/css/app.css`, `webapp/tests/conftest.py`, `webapp/tests/test_api.py`, `webapp/tests/test_templates.py`
- Modify: `pyproject.toml` (add `[tool.uv.workspace]`), `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/README.md`, `.env.example`, `.github/workflows/ci.yml`, `CHANGELOG.md`, `tests/test_placeholders.py`, `tests/test_agent_instructions.py`
- Test: `webapp/tests/test_api.py`, `webapp/tests/test_templates.py`, root `tests/test_placeholders.py`, `tests/test_agent_instructions.py`

**Interfaces:**
- Produces: `hinigram.contracts.Thresholds` (pydantic model: `rr_min`, `rr_max`, `rr_watch`, `plv_min`, `plv_unsteady`, `apnea_flat_s`, `motion_max_s`, `min_breaths`, `amp_floor_db`) and `hinigram.contracts.Health` (`ok: bool`, `source: str`, `detail: str`, `last_frame_age_ms: int | None`).
- Produces: `hinigram.config.Settings` (fields below) and `hinigram.config.Settings.thresholds() -> Thresholds`; `hinigram.app.create_app(settings: Settings | None = None, *, source=None, clock=None) -> FastAPI`; `hinigram.cli.main(argv: list[str] | None = None) -> int`.
- Produces: route `GET /` → 200 HTML, `GET /healthz/station` → `Health` JSON.

- [ ] **Step 1: Branch, and update the spec pull request with main first**

```powershell
cd C:\Users\Andrew\Desktop\Gengineer\gengineer-pjdsc-2026
git fetch origin --prune
git switch docs/webapp-design-spec
git merge --no-edit origin/main      # dependabot bumps only; no conflict expected
git push origin docs/webapp-design-spec
git switch -c feat/webapp-kiosk-station
```

PR #3 (`docs/webapp-design-spec` → `main`) carries the approved design. If it is still open when
the work is done, the feature PR stacks on it; if it has merged, branch from `origin/main`.

- [ ] **Step 2: Write the failing lane tests**

`tests/test_placeholders.py` becomes the "the decision is recorded" test (replace all three bodies):

```python
def test_webapp_readme_records_the_framework_decision(repo_root: Path) -> None:
    content = (repo_root / "webapp/README.md").read_text(encoding="utf-8").lower()
    assert "fastapi" in content and "jinja2" in content
    assert "2026-10-17" in content


def test_webapp_owns_its_manifest(repo_root: Path) -> None:
    assert (repo_root / "webapp/pyproject.toml").is_file()
    assert (repo_root / "webapp/uv.lock").is_file()


def test_webapp_suite_is_present(repo_root: Path) -> None:
    assert (repo_root / "webapp/tests").is_dir()
```

In `tests/test_agent_instructions.py`, replace `test_webapp_agents_withholds_framework_decision`
with `test_webapp_agents_records_the_framework_decision`: assert `"fastapi"` and `"no node"`
appear in `webapp/AGENTS.md`.

- [ ] **Step 3: Run them to verify they fail**

Run: `$env:UV_CACHE_DIR="$PWD\.uvcache"; uv run --no-sync pytest tests/test_placeholders.py tests/test_agent_instructions.py -q`
Expected: FAIL — `webapp/README.md` still says no framework, no manifest, no suite.

- [ ] **Step 4: Rewrite the lane documents and the two root documents that mirror them**

`webapp/README.md` opens with the dated decision:

> **Decision (2026-10-17): FastAPI + Jinja2 + vanilla JS on canvas, one process, no Node
> toolchain.** This lane is no longer a placeholder. `uv run hinigram` serves the screening
> station; the design record is [`../specs/2026-10-17-webapp-design.md`](../specs/2026-10-17-webapp-design.md)
> and the kiosk build is [`../specs/2026-10-17-webapp-kiosk-plan.md`](../specs/2026-10-17-webapp-kiosk-plan.md).

Then: the quickstart (`cd webapp && uv sync && uv run hinigram`), the commands table, the demo
scenario table (from `hinigram/fixtures/scenarios.json`), the privacy statement ("nothing is
measured before Start; nothing is stored"), the local gate commands, and the note that the staff
surfaces and the phase-space torus are deferred. Keep the file under 120 lines and make every
relative link resolve (root `tests/test_docs.py` link-checks it).

`webapp/AGENTS.md` keeps its shape but flips its first section: the framework **is** decided;
state the decision, the module boundaries (`pipeline/`, `station.py` import no FastAPI;
`app.py` imports them), the "no Node toolchain, no external assets, no CDN" rule, the
"patient copy lives in Python, JS renders it" rule, and that `webapp/` owns its manifest.
Keep it under 200 lines (root test asserts the budget).

Root `README.md`: change the `webapp/` map row to
``| [`webapp/`](webapp/) | Web | built | The screening station: FastAPI + Jinja2, no build step. `cd webapp && uv sync && uv run hinigram`. |``
and add the legend bullet ``- **built** — the lane's feature is implemented and runs from a clean clone.``
Leave every other map row alone (root tests parse this table). Add one sentence to the
Quickstart section pointing at the station, written as a single `cd webapp && …` line so root
`tests/test_quickstart.py` does not treat `hinigram` as a root-installed tool.

Root `AGENTS.md`: change the lane-map row to
``| `webapp/` | Python 3.12 via `uv` (FastAPI, Jinja2, vanilla JS) | Served by `uv run hinigram` | [`webapp/AGENTS.md`](webapp/AGENTS.md) |``
and replace the "no framework chosen" lane reminder with the real rules: own manifest and
lockfile, no Node, no external assets, no persistence of session data, patient copy in Python.

`docs/ARCHITECTURE.md`: line 23 row becomes
``| Web | `webapp/` | Python 3.12 via `uv` — FastAPI, Jinja2, vanilla JS on canvas | Served over HTTP by `uv run hinigram` | The screening station a patient stands in front of. |``
and §4's paragraph becomes a statement that the manifest now exists, the root project gained
`tool.uv.workspace` exclusion, and the second environment is deliberate.

`docs/README.md`: add a row for
[`../specs/2026-10-17-webapp-kiosk-plan.md`](../specs/2026-10-17-webapp-kiosk-plan.md).

`.env.example`: replace the `APP_BASE_URL` / `APP_HOST` / `APP_PORT` block with the keys the
station actually reads — `HINIGRAM_SOURCE`, `HINIGRAM_HOST`, `HINIGRAM_PORT`,
`HINIGRAM_SCENARIO`, `HINIGRAM_CAPTURE_S`, `HINIGRAM_SETTLE_S` — each with its default as the
placeholder and a one-line comment. Keep the sensor-node and notebook blocks untouched.

`CHANGELOG.md`: a `### Added` entry under `[Unreleased]` describing the station, the simulator,
and the three outcomes.

- [ ] **Step 5: Write the webapp manifest and lockfile**

```toml
[project]
name = "hinigram"
version = "0.1.0"
description = "Self-service respiratory screening station."
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn>=0.30,<1",
  "jinja2>=3.1,<4",
  "numpy>=2.0,<3",
  "scipy>=1.13,<2",
  "pydantic>=2.8,<3",
  "pydantic-settings>=2.4,<3",
  "pyserial>=3.5,<4",
]

[project.scripts]
hinigram = "hinigram.cli:main"

[dependency-groups]
dev = ["pytest>=8.3", "httpx>=0.27", "ruff==0.17.0", "mypy>=1.11"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["hinigram"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
files = ["hinigram"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra --strict-markers"
```

Run: `cd webapp; $env:UV_CACHE_DIR="..\.uvcache"; uv lock; uv sync` — expect a lockfile and an
installed environment, no network at run time afterwards.

Root `pyproject.toml`: append `[tool.uv.workspace]` with `exclude = ["webapp"]`, then
`cd ..; uv sync --locked; uv run --no-sync pytest -q` must stay green.

- [ ] **Step 6: Implement `Settings`, `create_app`, the kiosk shell, and the CLI**

`hinigram/config.py`:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HINIGRAM_", env_file=None)
    source: Literal["sim", "replay", "serial"] = "sim"
    serial_port: str | None = None
    replay_file: Path = PACKAGE_DIR / "fixtures" / "replay_session.jsonl.gz"
    scenario: str = "regular"
    host: str = "127.0.0.1"
    port: int = 8765
    settle_s: float = 3.0
    capture_s: float = 30.0
    result_hold_s: float = 20.0
    rr_min: float = 8.0
    rr_max: float = 24.0
    rr_watch: float = 20.0
    plv_min: float = 0.60
    plv_unsteady: float = 0.40
    apnea_flat_s: float = 10.0
    motion_max_s: float = 2.0
    min_breaths: int = 3
    amp_floor_db: float = -40.0
    presence_snr: float = 0.15
    sample_hz: float = 100.0

    def thresholds(self) -> Thresholds: ...
```

`hinigram/app.py` builds `FastAPI(lifespan=...)` with a `Jinja2Templates` directory
`Path(__file__).parent / "templates"`, a `StaticFiles` mount at `/static`, and the two routes.
`create_app` accepts `settings`, `source`, and `clock` so tests can inject all three; when
`station` wiring lands in Task 9 the same signature keeps working. For this task the routes are
`GET /` (renders `kiosk.html`) and `GET /healthz/station` (returns `Health` built from
`settings.source` with `ok=False`, `detail="starting"`, `last_frame_age_ms=None`).

`hinigram/cli.py` parses `--source`, `--serial-port`, `--replay-file`, `--host`, `--port`,
`--scenario`, `--settle-s`, `--capture-s`, `--plv-threshold`, `--rr-max`, `--verbose`; prints
`Hinigram station — http://127.0.0.1:8765 (source: sim)` and calls `uvicorn.run(app, host=,
port=, log_level=)`. A non-loopback `--host` prints `warning: binding {host}; this is not the
documented single-operator configuration` before starting.

`hinigram/templates/base.html` holds `<html lang="en">`, the viewport meta, the stylesheet link
to `/static/css/app.css`, and a `{% block content %}`. `kiosk.html` contains the header
(brand `Hinigram / Screening station`, a status area with a dot **and** the word `Station ready`,
a `HH:MM:SS` clock, no Staff link), the two cards (`#stage` canvas inside a stage card,
`#panel` with `aria-live="polite"` and a `Starting the station…` placeholder), the disclaimer
bar, and the three script tags. This task ships the shell only; Tasks 10–12 fill it.

`hinigram/static/css/app.css` gets the tokens and the page skeleton in this task (grid, cards,
header, disclaimer, buttons, typography with a 16 px floor) so the visual gate can start early.

- [ ] **Step 7: Write the first route tests and run them**

`webapp/tests/conftest.py` provides `settings_factory()` (a `Settings` with temp paths), and
`client(settings)` yielding `fastapi.testclient.TestClient(create_app(settings))` from a `with`
block, so the lifespan runs.

```python
def test_station_page_returns_html_with_disclaimer(client):
    body = client.get("/").text
    assert "Research prototype" in body
    assert "not a diagnosis" in body


def test_station_page_references_no_external_host(client):
    body = client.get("/").text
    assert "http://" not in body and "https://" not in body


def test_healthz_reports_the_source(client):
    payload = client.get("/healthz/station").json()
    assert payload["source"] == "sim" and payload["ok"] is False
```

Run: `uv run pytest tests/test_api.py tests/test_templates.py -q` → PASS.
Then the lane gates: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`.

- [ ] **Step 8: Add the webapp CI job**

In `.github/workflows/ci.yml`: add `webapp: ${{ steps.changed.outputs.webapp }}` to the
`changes` job outputs, compute it with `if grep -q '^webapp/' changed-files.txt; then echo
"webapp=true" >> "$GITHUB_OUTPUT"; else echo "webapp=false" >> "$GITHUB_OUTPUT"; fi`, add a
job `webapp` guarded on `needs.changes.outputs.webapp == 'true'` that checks out, installs uv,
then runs `uv sync --locked`, `uv run ruff format --check .`, `uv run ruff check .`,
`uv run mypy`, `uv run pytest -q` **with `working-directory: webapp`**, and add `webapp` to
`ci-success`'s `needs` list. Root `tests/test_github_config.py` pins that every job is guarded
by its own output name and that `ci-success` needs list stays closed.

- [ ] **Step 9: Run every gate, then commit**

```powershell
cd webapp; uv run ruff format .; uv run ruff format --check .; uv run ruff check .; uv run mypy; uv run pytest -q
cd ..; uv run ruff format --check .; uv run ruff check .; uv run mypy; uv run pytest -q
git add -A; git commit -m "feat(webapp): scaffold the station lane with FastAPI and record the decision"
```

Expected: both suites green (root: 114+ passing), formatting clean.

---

### Task 2: Frame contract, parser, and ring buffers

**Files:**
- Modify: `webapp/hinigram/contracts.py` (add `Frame` and `TxName`; the ring buffer types stay in `frames.py`)
- Create: `webapp/hinigram/pipeline/__init__.py`, `webapp/hinigram/pipeline/frames.py`
- Test: `webapp/tests/test_frames.py`

**Interfaces:**
- Produces: `contracts.Frame`, `contracts.TxName`, `contracts.Thresholds` (all pydantic v2).
- Produces: `frames.parse_frame_line(line: str | bytes) -> Frame | None` (None means malformed).
- Produces: `frames.TxRing` with `push(frame)`, `window(start_ms: float, end_ms: float) -> Window | None`, `last_t() -> int | None`; `frames.FrameStore` with `push(frame)`, `window(start_ms, end_ms) -> dict[str, Window]`, `reset()`, `counters() -> SourceCounters`; `frames.Window` dataclass `t: np.ndarray (n,)`, `phase: np.ndarray (n, ch)`, `amp: np.ndarray (n, ch)`, `fs: float`; `frames.SourceCounters` dataclass `frames: int`, `malformed: int`, `per_tx: dict[str, int]`, `last_t: int | None`.
- Consumes: nothing.

- [ ] **Step 1: Write the failing tests**

```python
def test_frame_roundtrips_through_the_parser():
    line = '{"v": 1, "t": 1792243200123, "tx": "tx2", "ch": 6, "seq": 42, "rssi": -42.5, "amp": [12, 14, 9], "phase": [-31, 5, 77]}'
    frame = parse_frame_line(line)
    assert frame is not None and frame.tx == "tx2" and frame.phase == [-31, 5, 77]


@pytest.mark.parametrize("line", ['{"t": 1, "tx": "tx1"}', "not json", "", '{"v": 9, "t": 1, "tx": "tx1"}'])
def test_malformed_lines_are_rejected(line):
    assert parse_frame_line(line) is None


def test_window_returns_only_frames_inside_the_range():
    store = FrameStore()
    for i in range(100):
        store.push(make_frame(t=1000 + i * 10, tx="tx1"))
    window = store.window(1100, 1400)
    assert window["tx1"].t.min() >= 1100 and window["tx1"].t.max() <= 1400
    assert window["tx1"].phase.shape[1] == 3


def test_ring_buffer_drops_the_oldest_frames():
    store = FrameStore(capacity=10)
    for i in range(25):
        store.push(make_frame(t=i * 10, tx="tx1"))
    assert store.counters().per_tx["tx1"] == 25
    assert store.window(0, 1000)["tx1"].t.shape[0] == 10


def test_reset_clears_every_channel():
    store = FrameStore()
    store.push(make_frame(t=10, tx="tx1"))
    store.reset()
    assert store.window(0, 1000) == {} and store.counters().frames == 0
```

`make_frame` is a conftest helper building a valid `Frame` with three subcarriers.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_frames.py -q` → FAIL, module not found.

- [ ] **Step 3: Implement the contract and the buffers**

`Frame` validates `v == 1`, `tx` in `{"tx1","tx2","tx3"}`, `amp`/`phase` lists of equal length;
`enforce_version` rejects an unknown `v` loudly (spec risk table) by returning None from the
parser and counting it malformed. `FrameStore` holds one `TxRing(capacity=4000)` per Tx (40 s at
100 Hz), a `collections.deque` of timestamps per ring, and numpy arrays written at a moving
index; `window` masks by timestamp and returns a copy (never a view) so callers cannot mutate
the buffer. `fs` is the median of `diff(t)` scaled to Hz, defaulting to `100.0` when fewer than
three samples exist.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_frames.py -q` → PASS. Then `uv run ruff format --check .`,
`uv run ruff check .`, `uv run mypy`.

- [ ] **Step 5: Commit**

```powershell
git add webapp/hinigram/contracts.py webapp/hinigram/pipeline webapp/tests/test_frames.py
git commit -m "feat(webapp): add the frame contract, parser, and ring buffers"
```

---

### Task 3: DSP primitives — filter, pick a transmitter, estimate the rate

**Files:**
- Create: `webapp/hinigram/pipeline/dsp.py`
- Modify: `webapp/tests/conftest.py` (add the `synth`, `fake_window`, `fake_series` helpers this task's tests use)
- Test: `webapp/tests/test_dsp.py`

**Interfaces:**
- Consumes: `frames.Window`.
- Produces: `hampel(x, window=7, n_sigma=3.0) -> np.ndarray`; `first_component(series: np.ndarray) -> np.ndarray` for `(n, ch) → (n,)`; `bandpass(x, fs, lo=0.2, hi=0.5, order=4) -> np.ndarray`; `band_snr(x, fs, lo=0.2, hi=0.5) -> float`; `best_transmitter(windows: dict[str, Window]) -> tuple[str, np.ndarray, float] | None` returning `(tx_name, bandpassed_series, snr)`; `estimate_rr(x, fs, lo=0.2, hi=0.5) -> tuple[float, int]` returning `(rr_bpm, breaths)`; `motion_seconds(window: Window, thresh_hz=3.0, rms_thresh=0.25) -> float`; `flat_seconds(x, fs, floor_ratio=0.25) -> float`; `rms_db(x) -> float`; `decimate(t, x, hz=10.0) -> tuple[np.ndarray, np.ndarray]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_rr_within_one_bpm_at_15(synth):
    x = synth(bpm=15.0, seconds=30.0, noise=0.02)
    rr, breaths = estimate_rr(bandpass(x, 100.0), 100.0)
    assert abs(rr - 15.0) <= 1.0 and breaths >= 5


def test_rr_within_one_bpm_at_26_4(synth):
    rr, _ = estimate_rr(bandpass(synth(bpm=26.4, seconds=30.0, noise=0.02), 100.0), 100.0)
    assert abs(rr - 26.4) <= 1.0


def test_hampel_removes_an_injected_spike(synth):
    x = synth(bpm=15.0, seconds=30.0, noise=0.0)
    spiked = x.copy(); spiked[500] += 6.0
    assert np.abs(hampel(spiked) - x).max() < 0.5


def test_bandpass_rejects_out_of_band_tones():
    t = np.arange(0, 30, 0.01)
    for hz in (0.05, 2.0):
        filtered = bandpass(np.sin(2 * np.pi * hz * t), 100.0)
        assert np.sqrt(np.mean(filtered**2)) < 0.1 * np.sqrt(np.mean(np.sin(2 * np.pi * hz * t) ** 2))


def test_best_transmitter_prefers_the_stronger_stream():
    windows = {"tx1": fake_window(gain=0.35), "tx2": fake_window(gain=0.15), "tx3": fake_window(gain=0.05)}
    name, series, snr = best_transmitter(windows)
    assert name == "tx1" and snr > 0.5 and len(series) == len(windows["tx1"].t)


def test_first_component_recovers_the_shared_signal():
    rng = np.random.default_rng(0)
    shared = np.sin(2 * np.pi * 0.25 * np.arange(3000) / 100)
    series = shared[:, None] + rng.normal(0, 0.05, (3000, 3))
    assert np.corrcoef(first_component(series), shared)[0, 1] > 0.95


def test_motion_seconds_counts_a_four_second_burst():
    clean = fake_window(gain=0.35)
    assert motion_seconds(clean) < 0.5
    assert motion_seconds(fake_window(gain=0.35, burst=(10.0, 14.0))) > 3.0


def test_flat_seconds_measures_a_pause():
    assert flat_seconds(fake_series(gain=0.35), 100.0) < 1.0
    assert abs(flat_seconds(fake_series(gain=0.35, flat=(10.0, 22.0)), 100.0) - 12.0) < 1.5
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_dsp.py -q` → FAIL.

- [ ] **Step 3: Implement the primitives**

- `hampel`: sliding median and MAD over `window`, replace values beyond `n_sigma * 1.4826 * MAD` with the local median (vectorised with `np.lib.stride_tricks.sliding_window_view`).
- `first_component`: mean-centre columns, `np.linalg.svd`, project on the first right singular vector, then multiply by `sign(corr(component, column mean))` so the sign is deterministic.
- `bandpass`: `scipy.signal.butter(order, [lo, hi], btype="bandpass", fs=fs, output="sos")` + `scipy.signal.sosfiltfilt`.
- `band_snr`: rFFT power; in-band power over total power (excluding the DC bin).
- `best_transmitter`: for each Tx, `first_component(unwrap(phase))` → `bandpass` → `band_snr` on the raw component; return the maximum, or None when fewer than 2 s of samples exist.
- `estimate_rr`: zero-pad the bandpassed series to 8× length, rFFT, argmax within `[lo, hi]`, parabolic interpolation on the log magnitude, `rr_bpm = peak_hz * 60`; `breaths` = positive-going zero crossings.
- `motion_seconds`: residual = series minus a 50-sample centred moving average; for each 0.5 s block compute the residual RMS; count blocks above `rms_thresh` and return the block count × 0.5.
- `flat_seconds`: envelope = rolling RMS over 1 s; threshold = `floor_ratio × median(envelope)`; longest contiguous run below threshold, in seconds.
- `decimate`: keep every `round(fs_target / median_dt)`-th sample starting at index 0.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_dsp.py -q` → PASS, then the three lane gates.

- [ ] **Step 5: Commit**

```powershell
git add webapp/hinigram/pipeline/dsp.py webapp/tests/test_dsp.py webapp/tests/conftest.py
git commit -m "feat(webapp): add the DSP primitives for rate estimation"
```

---

### Task 4: Hopf oscillator, Hilbert phase, and PLV

**Files:**
- Create: `webapp/hinigram/pipeline/hopf.py`
- Modify: `webapp/tests/conftest.py` (add the `plv_score` helper)
- Test: `webapp/tests/test_hopf.py`

**Interfaces:**
- Produces: `HopfParams` (frozen dataclass `mu=-0.5`, `omega=2*math.pi*0.25`, `gain=1.0`); `integrate(x: np.ndarray, fs: float, params: HopfParams = HopfParams()) -> np.ndarray` (complex, len == len(x)); `analytic_phase(x) -> np.ndarray`; `plv(phi_a, phi_b) -> float`; `winding(phi_a, phi_b, breaths: int) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
def test_plv_is_one_for_identical_phase():
    phi = np.linspace(0, 20 * np.pi, 3000)
    assert plv(phi, phi) > 0.999


def test_plv_is_near_zero_for_independent_phase():
    rng = np.random.default_rng(1)
    assert plv(rng.uniform(0, 2 * np.pi, 3000), rng.uniform(0, 2 * np.pi, 3000)) < 0.1


def test_locked_rhythm_has_high_plv_and_winding_near_one(synth):
    x = bandpass(synth(bpm=15.0, seconds=30.0, noise=0.01), 100.0)
    z = integrate(x / np.sqrt(np.mean(x**2)), 100.0)
    phi_breath = analytic_phase(x)
    value = plv(phi_breath, np.angle(z))
    assert value > 0.85
    assert 0.85 < winding(phi_breath, np.angle(z), breaths=7) < 1.15


def test_plv_falls_when_the_rate_jitters(synth):
    steady = bandpass(synth(bpm=15.0, seconds=30.0, noise=0.01, jitter=0.0), 100.0)
    jittered = bandpass(synth(bpm=15.0, seconds=30.0, noise=0.01, jitter=0.06), 100.0)
    assert plv_score(jittered) < 0.4 < 0.85 < plv_score(steady)
```

`plv_score(x)` is a conftest helper that normalises, integrates, and returns the PLV.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_hopf.py -q` → FAIL.

- [ ] **Step 3: Implement**

`integrate`: normalise `x` to unit RMS; RK4 per sample with the frame `dt = 1/fs`; the cubic
term is `abs(z)**2 * z`; `z` starts at 0. Return the complex trajectory.
`analytic_phase`: `np.angle(scipy.signal.hilbert(x))`.
`plv`: `abs(np.mean(np.exp(1j * (phi_a - phi_b))))`.
`winding`: unwrap `phi_a - phi_b`, take the total span, divide by `2π × breaths`, clamp to
`[-4, 4]`; return `1.0` when `breaths == 0`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_hopf.py -q` → PASS, then the three lane gates.

- [ ] **Step 5: Commit**

```powershell
git add webapp/hinigram/pipeline/hopf.py webapp/tests/test_hopf.py
git commit -m "feat(webapp): add the Hopf oscillator and phase-locking value"
```

---

### Task 5: Outcome rules and every word the patient reads

**Files:**
- Create: `webapp/hinigram/pipeline/analyze.py`, `webapp/hinigram/pipeline/rules.py`
- Modify: `webapp/hinigram/contracts.py` (add `Outcome`, `RuleName`, `Advice`, `Confidence`, `Metric`, `StaffDetails`, `Chip`, `StepState`, `Result`), `webapp/tests/conftest.py` (add the `analysis` helper)
- Test: `webapp/tests/test_analyze.py`, `webapp/tests/test_rules.py`

**Interfaces:**
- Consumes: `dsp.*`, `hopf.*`, `contracts.*`.
- Produces: `analyze.Analysis` (frozen dataclass: `tx_used`, `rr_bpm`, `plv`, `breaths`, `motion_s`, `flat_s`, `amp_db`, `usable_s`, `banded`, `t`, `phi_breath`, `phi_osc`, `locked`, `winding`, property `no_breath`); `analyze.analyze_window(windows: dict[str, Window], thresholds: Thresholds) -> Analysis | None`.
- Produces: `rules.decide(a: Analysis, t: Thresholds) -> Result`; `rules.stage_label(state, result) -> str`; `rules.chip_for(state, quality, result) -> Chip | None`; `rules.steps_for(state) -> list[StepState]`; `rules.STEP_LABELS == ("Stand on the mark", "Stay still · 30 s", "Result")`; `rules.patient_copy(outcome, advice) -> tuple[str, str]`.

- [ ] **Step 1: Write the failing rule tests**

```python
def test_motion_forces_unclear(analysis):
    result = decide(analysis(motion_s=2.5), default_thresholds())
    assert (result.outcome, result.rule) == ("unclear", "low_quality")


def test_few_breaths_force_unclear(analysis):
    assert decide(analysis(breaths=2), default_thresholds()).outcome == "unclear"


def test_apnea_needs_ten_flat_seconds(analysis):
    assert decide(analysis(rr_bpm=15, plv=0.9, flat_s=9.9), default_thresholds()).rule != "apnea"
    apnea = decide(analysis(rr_bpm=15, plv=0.9, flat_s=10.1), default_thresholds())
    assert (apnea.outcome, apnea.rule) == ("irregular", "apnea")


def test_tachypnea_needs_both_conditions(analysis):
    assert decide(analysis(rr_bpm=26.4, plv=0.7), default_thresholds()).rule != "tachypnea"
    assert decide(analysis(rr_bpm=26.4, plv=0.5), default_thresholds()).rule == "tachypnea"


def test_unsteady_needs_plv_below_040(analysis):
    assert decide(analysis(rr_bpm=16, plv=0.45), default_thresholds()).rule == "none"
    assert decide(analysis(rr_bpm=16, plv=0.35), default_thresholds()).rule == "unsteady"


def test_regular_band_and_watch_advice(analysis):
    assert decide(analysis(rr_bpm=15, plv=0.8), default_thresholds()).advice == "none"
    watched = decide(analysis(rr_bpm=22, plv=0.8), default_thresholds())
    assert watched.outcome == "regular" and watched.advice == "watch"


def test_every_outcome_has_patient_copy():
    for outcome, advice in (("regular", "none"), ("irregular", "speak_to_nurse"), ("unclear", "try_again")):
        headline, lede = patient_copy(outcome, advice)
        assert headline and lede and headline != lede


def test_result_carries_numbers_and_thresholds(analysis):
    result = decide(analysis(rr_bpm=26.4, plv=0.31, breaths=7), default_thresholds())
    assert result.rr_bpm == 26.4 and result.plv == 0.31
    assert [m.label for m in result.metrics] == ["Breathing rate", "Rhythm"]
    assert result.metrics[0].value == "26.4" and result.metrics[0].unit == "breaths / min"
    assert result.rhythm == "Unsteady" and result.flagged is True
    assert result.details.plv_threshold == 0.60
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_rules.py -q` → FAIL.

- [ ] **Step 3: Implement rules first, in the spec's order**

`decide` evaluates, first match wins: quality gate (`motion_s > motion_max_s` or
`breaths < min_breaths` or `amp_db < amp_floor_db` or `plv is None` → `unclear/low_quality`) →
`flat_s >= apnea_flat_s` → `irregular/apnea` → `rr_bpm > rr_max and plv < plv_min` →
`irregular/tachypnea` → `plv < plv_unsteady` → `irregular/unsteady` → `rr_min <= rr <= rr_watch
and plv >= plv_min` → `regular/none` → `rr_watch < rr <= rr_max or plv_unsteady <= plv < plv_min`
→ `regular/none` + `advice="watch"` → otherwise `unclear/low_quality`. Confidence is `high` when
the quality gate passed and `breaths >= 5`, `low` when `3 <= breaths < 5`, `none` otherwise; a
non-high confidence downgrades a clinical outcome to `unclear/low_quality`.

Patient copy (exact strings, asserted by tests):

| outcome | advice | headline | lede |
|---|---|---|---|
| regular | none | Breathing looks regular | No action needed. You can step away. |
| regular | watch | Breathing looks regular | Worth mentioning to staff if you feel unwell. Otherwise you can step away. |
| irregular | speak_to_nurse | Irregular breathing | Please speak to the nurse at the desk before you leave. |
| unclear | try_again | Reading not clear | Please try again. Stand still and breathe normally. |

`stage_label` per state: `idle` → `No one detected`; `settle`/`measuring` → `Measuring · stand
still`; `result` → `Irregular breathing detected` / `Breathing looks regular` / `Reading not
clear`. `chip_for`: measuring with `quality == "ok"` → `In position` (tone `ok`); measuring with
`quality == "low"` → `Keep still` (tone `warn`); result irregular → `Flagged for assessment`
(tone `warn`); result unclear → `Try again` (tone `warn`); otherwise None. `steps_for` marks
index < current `done`, == current `on`, > current `todo`, with state order
`idle/settle` → 1, `measuring` → 2, `result` → 3.

- [ ] **Step 4: Implement `analyze_window` and its test**

```python
def test_analyze_returns_numbers_for_a_clean_window(generated_window):
    analysis = analyze_window(generated_window(bpm=15.0, gain=0.35), default_thresholds())
    assert abs(analysis.rr_bpm - 15.0) <= 1.0
    assert analysis.tx_used == "tx1" and analysis.plv > 0.6
    assert analysis.motion_s < 1.0
```

`analyze_window` unwraps each Tx's phase, runs `best_transmitter`, bandpasses the chosen series,
estimates RR and breaths, computes motion/flat/amp, Hilbert phase, the driven oscillator, PLV and
winding, and returns None when no Tx has ≥ 2 s of samples. `usable_s` is the chosen window
duration in seconds.

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_rules.py tests/test_analyze.py -q` → PASS, then the lane gates.

- [ ] **Step 6: Commit**

```powershell
git add webapp/hinigram/pipeline/analyze.py webapp/hinigram/pipeline/rules.py webapp/tests/test_rules.py webapp/tests/test_analyze.py
git commit -m "feat(webapp): add the outcome rules and patient copy"
```

---

### Task 6: The simulator and its seven demo scenarios

**Files:**
- Create: `webapp/hinigram/fixtures/scenarios.json`, `webapp/hinigram/sources.py`
- Test: `webapp/tests/test_sources.py`

**Interfaces:**
- Consumes: `contracts.Frame`, `frames.FrameStore`, `analyze.analyze_window`, `rules.decide`.
- Produces: `sources.Scenario` (frozen dataclass `rr_bpm`, `jitter`, `noise`, `gains: tuple[float, float, float]`, `apnea: tuple[float, float] | None`, `motion: tuple[float, float] | None`, `label: str`); `sources.load_scenarios(path: Path | None = None) -> dict[str, Scenario]`; `sources.simulate_frames(scenario: Scenario, start_ms: int, n: int, fs: float = 100.0, seed: int = 0) -> list[Frame]`; `sources.Source` protocol (`name: str`, `start(store)`, `stop()`, `on_session_start(at_ms: int)`); `sources.SimulatorSource`, `sources.ReplaySource`, `sources.SerialSource`; `sources.build_source(settings: Settings) -> Source`.

- [ ] **Step 1: Write the failing simulator tests**

```python
def test_frames_are_deterministic_for_a_seed():
    scenario = load_scenarios()["regular"]
    first = simulate_frames(scenario, start_ms=0, n=3301)
    second = simulate_frames(scenario, start_ms=0, n=3301)
    assert [f.phase for f in first] == [f.phase for f in second]
    assert simulate_frames(scenario, start_ms=0, n=3301, seed=7)[900].phase != first[900].phase


def test_frames_cover_three_transmitters_and_three_subcarriers():
    frames = simulate_frames(load_scenarios()["regular"], start_ms=0, n=330)
    assert {"tx1", "tx2", "tx3"} == {f.tx for f in frames}
    assert {len(f.phase) for f in frames} == {3}
    assert [f.t for f in frames if f.tx == "tx1"][:3] == [0, 10, 20]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_sources.py -q` → FAIL.

- [ ] **Step 3: Implement the generator and the scenarios**

Each Tx emits frames at `fs`; frame `i` has `t = start_ms + round(i * 1000 / fs)` and
`ch = 3`, `seq = i`, `rssi = -42.5 - 3 * k`. Phase per subcarrier:
`base_k + gains[k] * s(t) + 0.05 * drift(t) + noise_k`, where `s(t)` is the respiration waveform
from the instantaneous rate `f(t) = rr_bpm/60 * (1 + jitter * band_limited_noise(t))`
(band-limited noise built from three sinusoids at 0.02/0.05/0.09 Hz with seeded phases, summed
and scaled), integrated to a phase angle, and `apnea` zeroes the respiratory term inside its
window. `motion` adds `amp * sin(2π * 6 Hz * t)` into the phase inside its window. A
scenario's timings are **seconds from session Start** (`on_session_start` resets the counter),
so the capture window lines up with the scripted event.

`fixtures/scenarios.json` — the values the plan proposed, then what the build actually ships.
The variability turned out to be the wrong knob (see deviation 6: a smooth frequency wobble
never lets the phase slip), so it was replaced by a breath-to-breath interval coefficient of
variation, and the numbers were re-tuned against measurement:

| name | rr_bpm (proposed → shipped) | variability (proposed → shipped) | apnea | motion | expected |
|---|---|---|---|---|---|
| regular | 15.0 → 15.0 | jitter 0.010 → cv 0.02 | — | — | regular / none |
| watch | 22.0 → 22.0 | jitter 0.020 → cv 0.05 | — | — | regular / none, advice watch |
| tachypnea | 26.4 → 28.0 | jitter 0.060 → cv 0.22 | — | — | irregular / tachypnea |
| unsteady | 16.0 → 22.0 | jitter 0.045 → cv 0.50, seed 3 | — | — | irregular / unsteady |
| apnea | 15.0 → 22.0 | jitter 0.010 → cv 0.02 | 10–22 s | — | irregular / apnea |
| motion | 15.0 → 15.0 | jitter 0.010 → cv 0.02 | — | 7–11 s | unclear / low_quality |
| absent | 15.0 → 15.0 | jitter 0.010 → cv 0.02 | 0–33 s (gains 0.0) | — | no respiratory signal: settle returns to idle |

- [ ] **Step 4: Add the end-to-end scenario test and tune `jitter` until it passes**

```python
@pytest.mark.parametrize("name,outcome,rule", [
    ("regular", "regular", "none"), ("watch", "regular", "none"),
    ("tachypnea", "irregular", "tachypnea"), ("unsteady", "irregular", "unsteady"),
    ("apnea", "irregular", "apnea"), ("motion", "unclear", "low_quality"),
])
def test_each_scenario_reaches_its_outcome(name, outcome, rule):
    window = analyse_scenario(name)          # conftest: simulate 33 s, window 3–33 s
    result = decide(window, default_thresholds())
    assert (result.outcome, result.rule) == (outcome, rule), (
        f"{name}: rr={window.rr_bpm:.1f} plv={window.plv:.2f} motion={window.motion_s:.1f} "
        f"flat={window.flat_s:.1f} breaths={window.breaths}"
    )
```

Tune **only** `jitter` (and, if a branch is unreachable, `noise`) in `scenarios.json` until the
six cases pass. Record the calibrated values in the JSON file itself. Do not weaken the test, and
do not special-case a scenario name anywhere in `pipeline/`.

- [ ] **Step 5: Implement the three sources**

- `SimulatorSource`: a thread that emits frames on a 10 ms grid up to wall-clock now, sleeping
  50 ms per batch; `on_session_start` resets the frame index so scenario timings are relative to
  Start; `stop()` joins the thread.
- `ReplaySource`: reads the gzipped JSONL, re-times the fixture's deltas to real time, and
  restarts from the top on `on_session_start`.
- `SerialSource`: opens `pyserial`, reads lines, `parse_frame_line` each, counts malformed
  frames, and reconnects after a 1 s pause when the port raises. Import `serial` lazily so a
  machine without pyserial can still run `--source sim`.
- `build_source(settings)`: `sim` → `SimulatorSource(settings.scenario)`, `replay` →
  `ReplaySource(settings.replay_file)`, `serial` → `SerialSource(settings.serial_port)` raising
  `ValueError("--serial-port is required for --source serial")` when the port is missing.

- [ ] **Step 6: Add the serial parser test with a fake stream**

```python
def test_serial_parser_survives_a_fragmented_and_a_malformed_line():
    source = SerialSource(port="FAKE", stream=FakeStream([b'{"v": 1, "t": 1, "tx"', b': "tx1", "ch": 3, "seq": 0, "rssi": -40, "amp": [1,2,3], "phase": [0,0,0]}\n', b"garbage\n"]))
    frames = list(source.read_frames())
    assert len(frames) == 1 and source.malformed == 1
```

- [ ] **Step 7: Run to verify pass**

Run: `uv run pytest tests/test_sources.py -q` → PASS (all six scenarios), then the lane gates.

- [ ] **Step 8: Commit**

```powershell
git add webapp/hinigram/sources.py webapp/hinigram/fixtures/scenarios.json webapp/tests/test_sources.py
git commit -m "feat(webapp): add the simulator and the six demo scenarios"
```

---

### Task 7: The replay fixture

**Files:**
- Create: `webapp/hinigram/fixtures/replay_session.jsonl.gz`
- Modify: `webapp/tests/conftest.py` (add the `iter_replay_fixture` and `analyse_fixture` helpers)
- Test: `webapp/tests/test_sources.py` (replay cases)

**Interfaces:**
- Consumes: `sources.simulate_frames`, `sources.Scenario`.
- Produces: a committed 33 s, 100 Hz, 3 Tx × 3 subcarrier replay file at
  `hinigram/fixtures/replay_session.jsonl.gz`, parseable by `parse_frame_line`.

- [ ] **Step 1: Write the failing replay tests**

```python
def test_replay_fixture_parses_into_a_full_session():
    frames = list(iter_replay_fixture())
    assert len(frames) > 9000
    assert {"tx1", "tx2", "tx3"} == {f.tx for f in frames}
    assert all(a.t <= b.t for a, b in zip(frames, frames[1:]))


def test_replay_fixture_reaches_a_regular_result():
    window = analyse_fixture(frames=list(iter_replay_fixture()))
    assert decide(window, default_thresholds()).outcome == "regular"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_sources.py -q -k replay` → FAIL (file missing).

- [ ] **Step 3: Generate the fixture from the simulator, once**

Run this inline script from `webapp/` (it is a generator, not a committed tool):

```powershell
uv run python -c "from pathlib import Path; import gzip, json; from hinigram.sources import load_scenarios, simulate_frames; s=load_scenarios()['regular']; frames=simulate_frames(s, start_ms=0, n=3301); p=Path('hinigram/fixtures/replay_session.jsonl.gz'); p.parent.mkdir(parents=True, exist_ok=True); gzip.open(p,'wt',encoding='utf-8',compresslevel=9).write(''.join(json.dumps(f.model_dump())+'\n' for f in frames))"
```

Expected: a file between 100 KB and 400 KB (a 1 MB tracked-file ceiling is enforced by the root
suite). If it exceeds 1 MB, regenerate with `simulate_frames(..., n=3301)` at `fs=100` and 3
subcarriers only — do not lower the sample rate, which would break the `100 Hz` contract.

- [ ] **Step 4: Run to verify pass, then commit**

Run: `uv run pytest tests/test_sources.py -q -k replay` → PASS.

```powershell
git add webapp/hinigram/fixtures/replay_session.jsonl.gz webapp/tests/test_sources.py
git commit -m "feat(webapp): commit a synthetic replay fixture for the offline demo"
```

---

### Task 8: The session state machine

**Files:**
- Create: `webapp/hinigram/station.py`
- Modify: `webapp/hinigram/contracts.py` (add `SessionState`, `LiveMetrics`, `Trace` — this task is their first consumer)
- Test: `webapp/tests/test_station.py`

**Interfaces:**
- Consumes: `frames.FrameStore`, `sources.Source`, `analyze.analyze_window`, `rules.*`, `contracts.*`.
- Produces: `station.monotonic_ms() -> int`; `station.StationError`, `station.SessionBusy`, `station.NotInResult`; `station.Station(store: FrameStore, settings: Settings, *, clock: Callable[[], int] = monotonic_ms, source: Source | None = None, id_factory: Callable[[], str] | None = None)` with a public `store` attribute, `state`, `start(scenario: str | None = None)`, `stop()`, `done()`, `tick()`, `snapshot() -> SessionState`, `trace() -> Trace | None`, `health() -> Health`.

- [ ] **Step 1: Write the failing state-machine tests**

```python
def test_idle_before_start(station):
    snapshot = station.snapshot()
    assert snapshot.state == "idle" and snapshot.result is None and snapshot.started_ms is None


def test_start_settles_then_measures(station, clock):
    station.start()
    assert station.snapshot().state == "settle"
    clock.advance(3_100); station.tick()
    assert station.snapshot().state == "measuring"


def test_nothing_is_measured_before_start(station):
    station.tick()
    assert station.snapshot().result is None and station.trace() is None


def test_stop_returns_to_idle_from_measuring(station, clock):
    station.start(); clock.advance(5_000); station.tick(); station.stop()
    assert station.snapshot().state == "idle" and station.snapshot().result is None


def test_result_arrives_after_capture_and_holds_then_resets(station, clock):
    station.start()
    clock.advance(33_500); station.tick()
    result = station.snapshot()
    assert result.state == "result" and result.result.outcome == "regular"
    clock.advance(20_100); station.tick()
    assert station.snapshot().state == "idle" and station.snapshot().result is None


def test_done_clears_the_result_immediately(station, clock):
    station.start(); clock.advance(33_500); station.tick(); station.done()
    assert station.snapshot().state == "idle"


def test_a_second_start_while_busy_is_refused(station):
    station.start()
    with pytest.raises(SessionBusy):
        station.start()


def test_done_outside_result_is_refused(station):
    with pytest.raises(NotInResult):
        station.done()


def test_the_next_session_gets_a_new_id(station, clock):
    station.start(); first = station.snapshot().id
    clock.advance(33_500); station.tick(); station.done()
    station.start()
    assert station.snapshot().id != first
```

The `station` fixture builds a `FrameStore` preloaded with `simulate_frames(load_scenarios()["regular"], start_ms=clock.now(), n=3301)` and passes `clock=clock.now` and `source=None`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_station.py -q` → FAIL.

- [ ] **Step 3: Implement the machine**

- `idle`: `start()` → new id (`s-` + `secrets.token_hex(3)`), `started_ms = clock()`, `store.reset()`, `source.on_session_start(started_ms)`, state `settle`.
- `settle`: at `settle_s`, analyse the settle window; when `analyze_window` is None or
  `presence` is False (`band_snr < settings.presence_snr`) or motion in settle > 2 s → back to
  `idle` with nothing recorded; otherwise `measuring`, `capture_started = clock()`.
- `measuring`: live metrics over `[capture_started, now]` once 5 s exist; at `capture_s`,
  analyse `[capture_started, now]`, `decide`, store the `Result` and the `Analysis` for
  `trace()`, state `result`.
- `result`: `clock() - result_at >= result_hold_s * 1000` → `idle`, result cleared.
- `stop()` allowed from `settle`/`measuring`/`result` → `idle`; `done()` only from `result` → `idle`.
- `snapshot()` builds `SessionState` with `duration_ms = (settle_s + capture_s) * 1000`,
  `elapsed_ms` measured from `started_ms` (0 when idle), `stage_label`/`chip`/`steps` from
  `rules`, and the stored `Result`.
- Guard every mutation with a `threading.Lock`; evaluation happens under the lock and takes a few
  milliseconds.
- `health()` reports `ok` when `store.counters().frames > 0` and the last frame is younger than
  3 s, with `detail` `Source connected` / `No frames yet`.

- [ ] **Step 4: Add the reset, buffer, and empty-zone tests**

```python
def test_the_next_session_cannot_see_the_previous_frames(station, clock):
    station.start(); clock.advance(33_500); station.tick(); station.done()
    assert station.snapshot().live is None
    assert station.store.window(0, clock.now()) == {}     # reset() cleared the buffers


def test_settle_without_respiration_returns_to_idle(empty_station, clock):
    empty_station.start()
    assert empty_station.snapshot().state == "settle"
    clock.advance(3_200); empty_station.tick()
    assert empty_station.snapshot().state == "idle"
    assert empty_station.snapshot().result is None
```

`empty_station` is the same fixture built with the `absent` scenario: noise only, gains `(0, 0, 0)`,
so `band_snr` stays under `settings.presence_snr` and settle must refuse to measure.

- [ ] **Step 5: Run to verify pass, then commit**

Run: `uv run pytest tests/test_station.py -q` → PASS, then the lane gates.

```powershell
git add webapp/hinigram/station.py webapp/tests/test_station.py
git commit -m "feat(webapp): add the session state machine"
```

---

### Task 9: Wire the HTTP API and the polling contract

**Files:**
- Modify: `webapp/hinigram/app.py`, `webapp/hinigram/cli.py`, `webapp/hinigram/config.py`
- Test: `webapp/tests/test_api.py`, `webapp/tests/test_contracts.py`

**Interfaces:**
- Consumes: `station.Station`, `frames.FrameStore`, `sources.build_source`.
- Produces: routes `GET /api/v1/session` → `SessionState`; `POST /api/v1/session?scenario=` →
  `SessionState`, 409 while busy, 400 for an unknown scenario or a scenario with a non-sim
  source; `POST /api/v1/session/stop` → `SessionState`; `POST /api/v1/session/done` →
  `SessionState`, 409 outside `result`; `GET /api/v1/session/trace` → `Trace`, 409 before a
  result; `GET /healthz/station` → `Health`.

- [ ] **Step 1: Write the failing API tests**

```python
def test_the_whole_flow_over_http(client, clock):
    assert client.get("/api/v1/session").json()["state"] == "idle"
    started = client.post("/api/v1/session", params={"scenario": "tachypnea"}).json()
    assert started["state"] == "settle" and started["id"].startswith("s-")
    clock.advance(3_200); client.get("/api/v1/session")
    assert client.get("/api/v1/session").json()["state"] == "measuring"
    clock.advance(30_000)
    finished = client.get("/api/v1/session").json()
    assert finished["state"] == "result"
    result = finished["result"]
    assert (result["outcome"], result["rule"]) == ("irregular", "tachypnea")
    assert abs(result["rr_bpm"] - 26.4) <= 1.0
    trace = client.get("/api/v1/session/trace")
    assert trace.status_code == 200 and trace.json()["tx_used"] == "tx1"
    assert client.post("/api/v1/session/done").json()["state"] == "idle"


def test_a_second_start_is_409(client):
    client.post("/api/v1/session")
    response = client.post("/api/v1/session")
    assert response.status_code == 409


def test_done_before_a_result_is_409(client):
    assert client.post("/api/v1/session/done").status_code == 409


def test_trace_before_a_result_is_409(client):
    assert client.get("/api/v1/session/trace").status_code == 409


def test_unknown_scenario_is_400(client):
    assert client.post("/api/v1/session", params={"scenario": "nope"}).status_code == 400


def test_session_payload_has_no_identifying_fields(client):
    payload = client.get("/api/v1/session").json()
    assert set(payload) <= {
        "id", "state", "source", "scenario", "started_ms", "elapsed_ms", "duration_ms",
        "presence", "quality", "motion", "stage_label", "chip", "steps", "live", "result",
    }
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_api.py -q` → FAIL (routes missing).

- [ ] **Step 3: Implement the lifespan, routes, and clock**

The lifespan creates `FrameStore`, `build_source(settings)`, and `Station(store, settings,
clock=clock or monotonic_ms, source=source)`, stores them on `app.state`, starts the source, and
starts an `asyncio` ticker:

```python
async def _tick_forever(station: Station) -> None:
    while True:
        station.tick()
        await asyncio.sleep(0.25)
```

Cancel it on shutdown, then `source.stop()`. Resource conflict: a `SessionBusy` maps to 409 and
`NotInResult` to 409 with a `{"detail": ...}` body. `--host` warning stays in `cli.py`.

- [ ] **Step 4: Add the contract tests**

`test_contracts.py` asserts `SessionState` validates a full payload; `Result` always carries
`thresholds`, `metrics`, `details` and non-empty `headline`/`lede`; `Trace.t` is decimated to
about 10 Hz (301 ± 5 samples over a 30 s window) and `Trace.plv` equals the result's `plv`.

Also update `test_healthz_reports_the_source` from Task 1: it must assert only the source token,
because once the source thread is running `ok` becomes time-dependent.

- [ ] **Step 5: Run to verify pass, then commit**

Run: `uv run pytest tests/test_api.py tests/test_contracts.py -q` → PASS, then the lane gates.

```powershell
git add webapp/hinigram/app.py webapp/hinigram/cli.py webapp/hinigram/config.py webapp/tests/test_api.py webapp/tests/test_contracts.py
git commit -m "feat(webapp): serve the station session over HTTP"
```

---

### Task 10: The kiosk page and stylesheet

**Files:**
- Modify: `webapp/hinigram/templates/kiosk.html`, `webapp/hinigram/templates/base.html`, `webapp/hinigram/static/css/app.css`
- Test: `webapp/tests/test_templates.py`, `webapp/tests/test_accessibility.py`

**Interfaces:**
- Consumes: `GET /` shell from Task 1; `app.js` globals `Hinigram.start()/stop()/done()/render(state)` and canvas element `#stage`.
- Produces: the DOM the client script binds to — `#stage`, `#panel`, `#stage-tag`, `#clock`, `#health`, `#health-word`, plus classes `.card`, `.stage`, `.panel`, `.steps`, `.metrics`, `.chip`, `.btn`, `.disc`.

- [ ] **Step 1: Write the failing template and accessibility tests**

```python
def test_the_page_carries_the_no_camera_caption(client):
    body = client.get("/").text
    assert "abstract guide" in body and "not a camera" in body


def test_the_panel_is_a_live_region(client):
    """The 'Details for staff' fold is rendered from the payload by app.js (Task 12);
    the shell must still announce state changes to a screen reader."""
    assert 'aria-live="polite"' in client.get("/").text


def test_html_references_only_local_assets(client):
    body = client.get("/").text
    assert "http://" not in body and "https://" not in body
    assert "/static/css/app.css" in body and "/static/js/app.js" in body


def test_every_font_size_is_at_least_sixteen_pixels():
    css = read_css()
    sizes = [float(m) for m in re.findall(r"font-size:\s*([0-9.]+)px", css)]
    assert sizes and min(sizes) >= 16


def test_primary_actions_are_at_least_fifty_six_pixels():
    css = read_css()
    assert re.search(r"\.btn\s*\{[^}]*min-height:\s*56px", css, re.S)


def test_focus_is_visible():
    assert ":focus-visible" in read_css()


def test_status_is_never_colour_alone(client):
    body = client.get("/").text
    assert 'id="health-word"' in body and "Station ready" in body


def test_the_source_is_named_on_the_surface(client):
    """REQ-103: simulated data must never look live."""
    body = client.get("/").text
    assert 'id="source-chip"' in body and "SIM" in body


def test_the_closed_page_leaks_no_plv_or_threshold(client):
    """AC-115: both live behind the collapsed staff fold, never in the shell."""
    body = client.get("/").text.lower()
    assert "plv" not in body and "0.60" not in body and "threshold" not in body
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_templates.py tests/test_accessibility.py -q` → FAIL.

- [ ] **Step 3: Port the mockup into the template**

Translate `final-kiosk.html`'s body structure (`main > .top`, `.wrap > .card.stage`,
`.card.panel`, `.disc`) into `kiosk.html`, with these deliberate differences:

- No "Preview state" row and no Staff link (staff routes are deferred).
- The panel's inner HTML is rendered by `app.js`; the template ships only the
  `Starting the station…` placeholder and the `aria-live="polite"` region.
- `#stage-tag` starts at `No one detected`; `#clock` shows `--:--:--` until the first poll;
  `#health` carries a dot plus `<span id="health-word">Checking…</span>`; `<span
  id="source-chip" title="data source">SIM</span>` is rendered server-side from the settings —
  `SIM` / `REPLAY` / `LIVE` for `sim` / `replay` / `serial` — so the honesty rule (REQ-103) never
  depends on JavaScript having run.
- The header keeps the brand `Hinigram / Screening station`.

`app.css` carries the mockup's tokens and components scaled for a 1280×720 kiosk: 16 px body,
`1.15fr 1fr` two-column grid with a 16 px gap, 14 px radius cards, the stage card with a
`#stage { width: 100%; height: 100%; display: block }` canvas, buttons at `min-height: 56px` and
18 px type, the three-step strip, metric cards, chips, and the disclaimer bar. Every colour is a
token from the spec's table; no hex literal appears outside `:root`.

- [ ] **Step 4: Run to verify pass, then commit**

Run: `uv run pytest tests/test_templates.py tests/test_accessibility.py -q` → PASS, then the
lane gates.

```powershell
git add webapp/hinigram/templates webapp/hinigram/static/css/app.css webapp/tests/test_templates.py webapp/tests/test_accessibility.py
git commit -m "feat(webapp): render the kiosk page and its design system"
```

---

### Task 11: The station scene on canvas

**Files:**
- Create: `webapp/hinigram/static/js/station.js`
- Modify: `webapp/hinigram/templates/kiosk.html` (script tag only)
- Test: manual visual verification (screenshots); no unit test — the JS has no business rule

**Interfaces:**
- Consumes: `#stage` canvas; `window.__HINIGRAM_RIG` constant.
- Produces: `window.StationScene = { init(canvas: HTMLCanvasElement), setState(state: object) }`
  where `state` is the `SessionState` payload; it reads `state.state`, `state.elapsed_ms`,
  `state.duration_ms`, `state.live?.rr_bpm`, `state.result?.outcome`, `state.result?.rr_bpm`,
  `state.result?.flagged`.

- [ ] **Step 1: Port the projection and the scene**

Copy the geometry and drawing routines from `final-kiosk.html` lines 107–271 —
`project`, `poly`, `floorArc`, `floorDisc`, `drawFloor`, `drawMark`, `drawNode`, `drawPerson`,
`drawTag`, `draw`, `resize` — into an IIFE exposing `StationScene`. Keep the camera
`{yaw: -0.34, pitch: 0.54, dist: 7.4, f: 800, tx: 0, ty: 0.82, tz: 0.15}`, the floor
`±2.2 m`, the mark radius `0.62 m`, and the mast positions `TX-1 (-1.55, -1.10)`,
`TX-2 (1.55, -1.10)`, `TX-3 (0.10, -1.95)`, `RX (1.60, 1.25)`.

- [ ] **Step 2: Drive it from the session state instead of the preview buttons**

- `idle`: dashed ring, no figure, `No one detected` tag.
- `settle` / `measuring`: figure at the mark breathing at `live.rr_bpm ?? 15`; the ring is a
  progress arc from `elapsed_ms / duration_ms`; the tag reads the server's `stage_label`.
- `result`: ring and mark pulse in the outcome colour — `#0f7b4f` regular, `#b3261e` irregular,
  `#8f5600` unclear — with the tag `IRREGULAR · 26.4 /min` style built from the result's word and
  RR (`REGULAR`, `NOT CLEAR` for the others); no fabricated breath tag when `rr_bpm` is null.
- Read the four outcome colours from `getComputedStyle(document.documentElement)` once at init
  and on resize, so `app.css` stays the only place a colour is defined.
- Under `prefers-reduced-motion`, stop the chest animation and the result pulse; keep the rings,
  the tag and the progress arc.
- Drag orbits yaw by ±0.5 rad and pitch by ±0.15 rad around the defaults; a double-click resets.
  `ResizeObserver` on the canvas re-derives `DPR`, `W` and `H`.
- Clear `requestAnimationFrame` on `pagehide` so a reload cannot stack animation loops.

- [ ] **Step 3: Verify visually at three sizes**

Start the station (`uv run hinigram`), then for each of `1280,720`, `1024,768`, `820,1180`:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu --window-size=1280,720 --screenshot="C:\Users\Andrew\Desktop\Gengineer\.superpowers\shots\stage-idle-1280.png" http://127.0.0.1:8765/
```

Compare against `shot-kiosk-idle.png`: the floor grid, the four masts with labels, the dashed
mark, and the caption must all be present, and the dashed ring must be inside the frame. The
figure appears only in `measuring`/`result` (use `?scenario=regular` and wait, or press Start).

- [ ] **Step 4: Commit**

```powershell
git add webapp/hinigram/static/js/station.js webapp/hinigram/templates/kiosk.html
git commit -m "feat(webapp): draw the station scene on canvas"
```

---

### Task 12: The client controller and the rhythm strip

**Files:**
- Create: `webapp/hinigram/static/js/app.js`, `webapp/hinigram/static/js/wave.js`
- Modify: `webapp/hinigram/templates/kiosk.html` (script tags)
- Test: `webapp/tests/test_templates.py` (asset presence and client-render assertions), manual browser verification

**Interfaces:**
- Consumes: `GET /api/v1/session`, `POST /api/v1/session?scenario=`, `POST /api/v1/session/stop`,
  `POST /api/v1/session/done`, `GET /api/v1/session/trace`, `GET /healthz/station`,
  `window.StationScene`, `window.Wave`.
- Produces: `window.Hinigram` with `refresh()`, `render(session)`, and button handlers.

- [ ] **Step 1: Implement the poller and renderer**

- On load: `refresh()` immediately, then poll every 250 ms while `settle`/`measuring` and every
  1000 ms otherwise; the timeout schedules the next poll after the previous one settles (no
  overlapping fetches).
- A failed fetch keeps the last render, sets `#health-word` to `Reconnecting…`, and retries in
  2 s; it never clears the panel.
- `render(session)` writes the panel for the three states from the payload: the stage label, the
  headline/lede (from `result` when present), the countdown
  `Math.ceil((duration_ms - elapsed_ms) / 1000)`, the progress bar width from
  `elapsed_ms / duration_ms`, the chip (text + tone class), the three-step strip from
  `steps`, and on `result` the two metric cards, the flagged chip, the `Details for staff`
  `<details>` with PLV, threshold, window, breaths, and a `<canvas id="spark">`, and the Done
  button.
- Buttons call the endpoints and then `refresh()`: Start posts `?scenario=` taken from
  `new URLSearchParams(location.search)` when present; Stop posts `/stop`; Done posts `/done`.
  Disable a button while its request is in flight.
- The primary action is one `.btn` whose label is `Start`, `Stop`, or `Done`, styled `.btn.crit`
  when the result is irregular; any secondary action uses `.btn.ghost`. Both are at least 56 px
  tall, and neither is ever a `<div>` with a click handler.
- The source chip stays in sync with `session.source` (`SIM` / `REPLAY` / `LIVE`), and is
  visible on every state — the patient-facing rule is that simulated data never looks live.
- The clock updates every second locally from the payload's `elapsed_ms` only for the countdown;
  the wall clock is `new Date().toLocaleTimeString('en-GB', {hour12: false})`.
- `#health` polls `/healthz/station` every 5 s and writes `Station ready` / `Source offline`
  next to the dot, so status is never colour alone.

- [ ] **Step 2: Implement the rhythm strip**

`wave.js` exposes `window.Wave = { draw(canvas, trace, colour) }`: app.js fetches
`/api/v1/session/trace` the first time the fold is opened, passes the payload to `Wave.draw`,
which decimates to the canvas width and draws the bandpassed amplitude around a faint zero line,
with `trace.plv` printed beside it. No fake waveform: if the trace request fails, the canvas
stays blank and the text says `trace unavailable`.

- [ ] **Step 3: Write the client-render assertions**

Because the panel is rendered from the payload, its content is asserted against the served
script rather than against the HTML:

```python
def test_the_staff_fold_is_part_of_the_client_render(client):
    js = client.get("/static/js/app.js").text
    assert "Details for staff" in js and "<details" in js


def test_the_client_never_invents_a_number(client):
    js = client.get("/static/js/app.js").text
    assert "Math.random" not in js          # every value comes from the payload
```

- [ ] **Step 4: Verify the three states in the browser**

With the station running, go to `http://127.0.0.1:8765/?scenario=tachypnea`, press Start, and
capture a screenshot at each state (`station-measuring.png`, `station-result.png`) into
`.superpowers/shots/`. The result must show `Irregular breathing`, `26.x breaths / min`,
`Unsteady`, the flagged chip, and the folded staff details — matching `shot-kiosk-result.png`
except for the deliberate size and wording differences.

- [ ] **Step 5: Verify the Review Focus behaviours by hand**

- Reload mid-measure: the countdown continues and the id does not change.
- Press Start twice quickly: one session, no error banner.
- Leave the result screen alone for 20 s: the panel returns to idle and the scene drops the
  figure.
- Reach a result with `?scenario=motion`: the outcome is `Reading not clear` with a Try again
  path and no RR metric, and Done available.
- Open a second tab mid-session: it shows the same session, and neither tab can start a new one.

- [ ] **Step 6: Commit**

```powershell
git add webapp/hinigram/static/js/app.js webapp/hinigram/static/js/wave.js webapp/hinigram/templates/kiosk.html webapp/tests/test_templates.py
git commit -m "feat(webapp): wire the kiosk client to the session API"
```

---

### Task 13: Acceptance pass, documentation, and the pull request

**Files:**
- Modify: `webapp/README.md`, `CHANGELOG.md`, `webapp/tests/test_api.py`, `webapp/tests/test_station.py`, `webapp/tests/test_contracts.py`
- Test: the full webapp suite, the root suite, and a clean-clone smoke run

**Interfaces:**
- Consumes: everything above.
- Produces: a green branch and a pull request.

- [ ] **Step 1: Write the acceptance tests this build still owes**

In `webapp/tests/test_api.py`:

```python
def test_a_refresh_rejoins_the_running_session(client, clock):
    started = client.post("/api/v1/session").json()
    clock.advance(5_000)
    assert client.get("/api/v1/session").json()["id"] == started["id"]


def test_two_tabs_cannot_start_two_sessions(client):
    client.post("/api/v1/session")
    assert client.post("/api/v1/session").status_code == 409
```

In `webapp/tests/test_station.py`:

```python
def test_a_stale_window_after_a_long_pause_is_unclear(station, clock):
    station.start()
    clock.advance(33_500 + 600_000)      # laptop slept for ten minutes
    station.tick()
    assert station.snapshot().result.outcome == "unclear"
```

This requires `tick()` to detect that the capture window has no frames inside the last
`capture_s` and force `unclear/low_quality` instead of analysing stale samples.

In `webapp/tests/test_contracts.py`:

```python
def test_evaluation_is_under_400_ms(clock):
    station = make_station(clock, scenario="regular")
    station.start(); clock.advance(33_500)
    started = time.perf_counter()
    station.tick()
    assert time.perf_counter() - started < 0.4
```

- [ ] **Step 2: Run the complete gate**

```powershell
cd C:\Users\Andrew\Desktop\Gengineer\gengineer-pjdsc-2026\webapp
$env:UV_CACHE_DIR = "C:\Users\Andrew\Desktop\Gengineer\gengineer-pjdsc-2026\.uvcache"
uv run ruff format --check .; uv run ruff check .; uv run mypy; uv run pytest -q
cd ..
uv run ruff format --check .; uv run ruff check .; uv run mypy; uv run pytest -q
```

Expected: webapp suite green in under 15 s; root suite green, now 114 + the rewritten lane tests.

- [ ] **Step 3: Prove the documented quickstart on a clean copy**

```powershell
$tmp = "C:\Users\Andrew\Desktop\Gengineer\.superpowers\clone-check"
git clone --no-local . $tmp
cd $tmp\webapp; $env:UV_CACHE_DIR="C:\Users\Andrew\Desktop\Gengineer\gengineer-pjdsc-2026\.uvcache"; uv sync --locked; uv run pytest -q
```

Expected: the suite passes from a fresh clone with no manual setup. Remove `$tmp` afterwards.

- [ ] **Step 4: Update the lane README and CHANGELOG with the verified reality**

`webapp/README.md`: quickstart, the scenario table (name → what the kiosk shows), the privacy
statement, the local gate, the deferred staff surfaces, and the honest limits — the detector is a
prototype, thresholds are prototype values, no evaluation artifact exists, and the station has
not been run against real hardware. `CHANGELOG.md`: one `Added` entry, dated, naming the kiosk,
the simulator, the six scenarios, and the deferrals.

- [ ] **Step 5: Commit, push, and open the pull request**

```powershell
cd C:\Users\Andrew\Desktop\Gengineer\gengineer-pjdsc-2026
git add -A; git commit -m "docs(webapp): document the station quickstart and its limits"
git push -u origin feat/webapp-kiosk-station
gh pr create --base main --head feat/webapp-kiosk-station --title "feat(webapp): build the kiosk screening station" --body-file <body>
```

The PR body summarises what/why/verification, names the `webapp` lane, states that the design
record is `specs/2026-10-17-webapp-design.md`, lists the deferred surfaces, and carries the
screenshot paths. If `main` already contains the design PR, base the branch on it; otherwise say
in the body that it stacks on PR #3.

---

## Spec coverage for this slice

| Requirement | Where it is met |
|---|---|
| REQ-101 one command, no Node | Task 1 manifest/CLI, Task 13 clean-clone check |
| REQ-102 runs with no hardware | Tasks 6, 7, 9 (simulator + replay) |
| REQ-103 source named on the surface | `Health` + `SessionState.source`; Task 10 renders `SIM`/`REPLAY`/`LIVE` server-side and tests it |
| REQ-104 one session, one state | Task 8 |
| REQ-105 nothing before Start | Tasks 8, 9, 13 |
| REQ-106 three outcomes + copy | Task 5, Task 12 |
| REQ-110 no identifiers | Task 2 contract, Task 9 payload test |
| REQ-111 disclaimer everywhere | Task 10 template test |
| REQ-112 accessibility floors | Task 10 accessibility tests |
| REQ-114 offline suite under 15 s | Task 13 Step 2 |
| REQ-117 loopback bind + warning | Task 1 CLI |
| REQ-119 no-camera caption | Task 10 template test |
| REQ-121 result ends and resets | Task 8, Task 13 |
| REQ-122 motion/low quality never confident | Tasks 5, 8, 13 |
| AC-101, AC-102, AC-105, AC-106, AC-108, AC-109, AC-110, AC-113, AC-114, AC-115, AC-116 | Tasks 1, 9, 10, 13 |
| AC-103 tachypnea yields irregular within 1 bpm and evaluates in under 400 ms | Tasks 6, 9, 13 |

**Deferred with the staff surfaces (not this build):** REQ-107–109 (backend graph, fault
attribution, latency display), REQ-113's on-screen demo buttons (replaced by the `?scenario=`
operator control, documented in the lane README — the reproducibility intent is kept),
REQ-115 (evaluation artifact), REQ-116 (method page), REQ-118's root-suite half is in Task 1
while the manifest half is here, REQ-120 (torus from staff details).

## Known deviations from the spec text

1. **Polling replaces SSE** (`§4`, `§6.2`). One 4 Hz `GET /api/v1/session` on loopback is
   simpler to test, has no reconnection semantics, and cannot wedge a kiosk behind a stalled
   stream. The state machine and the payload are unchanged.
2. **The result panel is rendered client-side** (`§10.1` mentions `kiosk_result`) so a session
   never reloads mid-measure. All patient copy still lives in Python (`rules.py`) and is tested
   there; the template tests assert the shell, the disclaimer, and the no-camera caption. The
   payload carries `headline`, `lede` and `hint` for that reason: the browser composes no
   sentence and no number.
3. **Fixtures live inside the package** (`hinigram/fixtures/`, not `webapp/fixtures/`) so the
   installed console script resolves them without a path guess.
4. **No SQLite store** (`§12`, D-8). The kiosk stores nothing at all, which is the strongest
   reading of REQ-110; the store returns with the staff sessions page.
5. **A `pipeline/analyze.py` module is added** between `dsp`/`hopf` and `station`, so the state
   machine stays timer-only and the orchestration is unit-testable without a clock.
6. **The phase-locking statistic measures phase diffusion, not filter lag** (`§7.2`). The spec's
   damped oscillator driven by the observed waveform tracks its driver, so the phase difference
   is a constant lag: measured across rate variability from 0 to 15 percent the statistic stayed
   between 0.88 and 0.93, and it cannot separate a steady rhythm from an irregular one. The
   implementation keeps the Hopf model, the oscillator, and the PLV definition, but the
   oscillator is the *autonomous limit cycle* whose frequency is learned from the window; PLV
   then asks whether each breath stays on that rhythm. Verified: a steady 15 and a steady 26.4
   breaths per minute both lock above 0.9, and irregular intervals fall below 0.4.
7. **The rate comes from the phase slope, not the spectral peak** (`§7.1` step 7). An irregular
   rhythm broadens its spectrum, and a peak estimate reads low: the tachypnea scenario scripted
   at 28 breaths per minute measured 23.5 and would not have crossed the 24 bpm threshold. The
   least-squares slope of the breath phase measured 27.2 on the same window. The spectral
   estimator remains in `dsp.estimate_rr` and is tested on clean tones.
8. **The breath pause is measured on a wide band with hysteresis** (`§7.1` step 8). The
   detector's narrow 0.2-0.5 Hz filter rings for several seconds at each edge of a pause and
   filled the pause with its own transient — a twelve-second pause measured three. The envelope
   is now taken from a second-order 0.1-1.0 Hz band, entering at a quarter of the median and
   leaving at half, and the same pause measures 10.2 seconds.
9. **One clock for the station and its sources.** The state machine runs on a monotonic clock;
   the simulator and the replay source stamp their frames with it too. During verification they
   did not: every frame landed decades outside the window being measured, which read as an empty
   zone and sent the station back to idle. `hinigram/clock.py` is the single source, and two
   regression tests pin the plumbing.
10. **A capture with a hole in it is not a measurement.** The plan's staleness check covered only
    the right edge of the window, so a dropout in the middle was analysed as if the phase were
    continuous: a ten-second hole still produced `regular`, `confidence: high`, and a staff fold
    that said "30.0 s window". `analyze.compute` now reports the longest gap and the seconds of
    data the window actually holds; a gap above `max_gap_s` (one second) is a `low_quality` gate,
    and `usable_s` is covered time rather than span. The consequence for the plan's own test is
    deliberate: a laptop that sleeps *after* a complete capture still reports its result, while a
    capture that lost frames must not — the former is a delay, the latter is missing data.
