# AGENTS.md — webapp lane

Scope: everything under `webapp/`. The closest `AGENTS.md` wins, so this file overrides the root
[`AGENTS.md`](../AGENTS.md) for these paths; the root file's repository-wide rules still apply.

## The framework is chosen

**FastAPI + Jinja2 + vanilla JavaScript on canvas, one process, no Node toolchain.** The decision,
its date, and the alternatives it rejected are recorded in
[`../specs/2026-10-17-webapp-design.md`](../specs/2026-10-17-webapp-design.md); the lane `README.md`
carries the dated summary. Do not re-litigate it in code review, and do not introduce a second
runtime to "modernise" the client.

## Hard rules

- **No Node toolchain, no build step, no bundler.** No `package.json`, no `node_modules/`, no
  transpiler, no CDN import. The browser loads the files in `hinigram/static/` exactly as written.
  Judge reproducibility outranks developer convenience (design record, D-1).
- **Nothing is measured before an explicit Start,** and nothing about a person is stored. No
  identifiers, no images, no camera, no audio, no session table. Session ids are random.
- **This lane owns its manifest and lockfile.** `pyproject.toml` and `uv.lock` live here, and the
  root `pyproject.toml` excludes the lane from its `tool.uv.workspace`. A root `uv sync` must not
  resolve this project.
- **Business rules live in Python, not JavaScript.** The client renders server-supplied copy and
  numbers; it never decides an outcome, formats a clinical value, or invents a waveform. Patient
  copy, thresholds, and the three outcomes live in `hinigram/pipeline/rules.py` and are tested
  there.
- **`pipeline/` and `station.py` import no FastAPI.** `app.py` imports them, never the reverse, so
  the detector and the state machine stay unit-testable without an HTTP client.
- **Patient surface accessibility is a requirement, not polish.** Body copy is at least 16 px,
  primary actions at least 56 px tall, status is never encoded by colour alone, and motion stops
  under `prefers-reduced-motion`.
- **One place for colour.** Every colour is a token in `hinigram/static/css/app.css`; templates and
  canvas code read tokens, they do not carry hex literals.
- **Tests run offline, with no hardware, deterministically.** Clocks are injected; no `time.sleep`
  in a test that could be a fake clock.
- **No secrets and no `.env`.** `.env` is prohibited repository-wide; committed fixtures are
  synthetic and labelled as such.
- **`../specs/` is frozen.** It is the record of what was decided; a change to the design is a new
  record, not an edit.

## Commands

    cd webapp && uv sync                     # environment from uv.lock
    cd webapp && uv run hinigram             # serve http://127.0.0.1:8765 (simulator)
    cd webapp && uv run pytest               # lane suite: offline, deterministic, < 15 s
    cd webapp && uv run ruff format .        # format
    cd webapp && uv run ruff check .         # lint
    cd webapp && uv run mypy                 # types

The four gates above mirror the root repository gate and the `webapp` CI job.

## Layout

`hinigram/pipeline/` is the signal path (frames → dsp → hopf → analyze → rules); `station.py` is
the session state machine; `sources.py` produces frames (simulator, replay, serial); `app.py` is
the HTTP shell; `templates/` and `static/` are the browser surface. Keep each file one
responsibility — a module that grows a second one is a module to split, not a module to document.

## Where to go next

- What the station does and how to run it: [`README.md`](README.md).
- Why it is shaped this way, including the deferred staff surfaces:
  [`../specs/2026-10-17-webapp-design.md`](../specs/2026-10-17-webapp-design.md).
- How it was built, task by task:
  [`../specs/2026-10-17-webapp-kiosk-plan.md`](../specs/2026-10-17-webapp-kiosk-plan.md).
