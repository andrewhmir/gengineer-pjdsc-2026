# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Repository history is Conventional Commits with a lane scope; this file is the
human-readable summary a judge or a returning teammate can read without walking the log.

## [Unreleased]

### Added

- **Hinigram live console** (`webapp/`, Node.js 20+, branch `webapp/node-live-console`): one local
  process (`cd webapp && npm ci && node src/server.js`, http://127.0.0.1:8780) that finds the receiver
  on USB by itself, runs every packet through the Hinigram v1.3.2 pipeline, and shows each transmitter's
  breathing rate, status, link health and a placement hint. **This replaces decision D-1 of
  `specs/2026-10-17-webapp-design.md` (FastAPI, no Node) and needs the team's agreement before it
  merges.** In detail:
  - the pipeline is `vendor/hinigram_dsp.js`, copied byte for byte from the v1.3.3 bundle (SHA-256
    `3eca8226…`); the only dependency is `serialport` 13;
  - the receiver connection holds DTR and RTS low (on these boards RTS high holds the ESP32 in reset),
    reads on through the boot text after a reset, reconnects after an unplug, knows a receiver by its
    start-up banner even with no transmitter on air, and leaves ports it identified as transmitters
    alone (opening a port resets the board on it);
  - a live raw signal from the first packet; an analysed breathing trace whose history never redraws
    (each 2 s hop is turned to match the overlap and joined without a step); a 2-minute pattern-strength
    strip; a held rate when the pipeline keeps a rate-based status; old readings marked stale;
  - an "Is it working?" check chain: receiver, data, transmitters heard (any number), link quality,
    serial-link load with room for more transmitters, breathing;
  - the v1.3.3 trained model (ResoNet `lin_sync-e80`, six models) as a labelled second opinion only,
    run by `model/resonet_sidecar.py` with the bundle's own code, never used for a status or alert
    (in the bundle's test it gave "no breathing concern" in 6 to 8 of 162 breath-hold windows, against 2);
  - recording to `data/raw/recordings/` in `log_serial.py`'s format, replay of a recording, and a
    simulated receiver (`npm run demo`, clearly marked) for use without hardware;
  - a **Boards panel**: lists every ESP32 on USB, identifies what each runs from its start-up log
    without writing anything, and writes a chosen role (receiver, or transmitter with an ID) from a
    chosen firmware version with esptool, telling the user when to hold BOOT and checking the result;
    gives universal transmitters a new ID without writing firmware;
  - a **firmware library** (`tools/build-firmware.js`): builds the team set (`csi_rx`, `csi_tx1..3`),
    the v1.3.3 bundle set and the universal set into `webapp/.firmware/library/<set>/<version>/`,
    outside the source folders, and keeps every version built; `tools/csi_rx.sdkconfig.defaults`
    supplies the two settings `csi_rx` needs that its folder does not record (CSI on, 921,600 baud);
  - 34 tests (`npm test`, `node:test`), using start-up logs the real boards printed.

- Web application design record: `specs/2026-10-17-webapp-design.md` settles the framework
  decision the bootstrap deferred — FastAPI, Jinja2, and vanilla JS on canvas, one process,
  no Node toolchain — and specifies a **self-service respiratory screening station**: a person
  stands on a marked spot, presses Start, and thirty seconds later reads one of three
  outcomes. It records the session state machine, the data contracts, the single-subject
  detector, the patient station scene, the staff phase-space torus, the backend graph with real
  HTTP probes, the fault-localisation rules, and the acceptance criteria. Three deviations
  from the proposal are stated, including that the product screens one person per session while
  multi-subject separation stays an offline result. Design only; no `webapp/` code has landed.
- Nine detection and accessibility sources recorded in `docs/SOURCES.md`, including the
  phase-locking value (Lachaux et al., 1999) and the Hopf oscillator (Righetti et al., 2006)
  the detector is built on, plus WCAG 2.2 as the accessibility standard for the interface.
- Firmware lane skeleton: `firmware/code.py` (the CircuitPython auto-run entry point) with
  hardware access behind a guarded, injectable seam, plus the lane `README.md` covering
  flashing, the pinned Adafruit bundle `20261010`, and the language subset. Templates
  `firmware/secrets.example.py` and `firmware/config.example.toml` are placeholders only.
  CI byte-compiles the lane; no board has been flashed yet.

### Changed

- `.gitignore`: `node_modules/` and `webapp/.firmware/` (the live console's firmware build output).

### Fixed

### Security

## [0.1.0] - 2026-10-10

The bootstrap: repository structure, toolchain, data policy, and governance. No data
analysis or firmware feature is implemented at this version.

### Added

- Root Python toolchain: `pyproject.toml` with `requires-python = ">=3.12"`, a pinned
  `uv.lock`, `.python-version`, and the development dependency group (`ruff` pinned
  exactly, `mypy`, `pytest`, `pytest-cov`, `nbmake`, `pre-commit`).
- `.editorconfig`, `.gitignore` (with no trailing comments on pattern lines, because a
  trailing comment turns a pattern into a never-matching literal), and
  `.pre-commit-config.yaml` (whitespace, end-of-file, YAML/TOML/JSON validity, large-file
  guard, merge-conflict guard, `ruff` lint and format, `nbstripout`).
- `.gitleaks.toml` with the default rule set extended and a narrow three-file allowlist
  for committed placeholder templates.
- Test suite with the `repo_root` fixture and repository smoke tests asserting the layout,
  the Python pin, and the presence of the scanner configuration.
- Documentation set: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`,
  `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/DATA.md`, `docs/SOURCES.md`, and
  `docs/SETUP.md`.
- Governance and citation: `LICENSE` (Apache License 2.0), `CITATION.cff` declaring the
  software entry and its authors, and `.env.example` as the committed template for the
  gitignored `.env`.
- Frozen design records in `specs/`: the approved repository bootstrap design and its
  implementation plan.

### Security

- Secret scanning is enforced by the `secrets` CI job using the free gitleaks CLI. No
  gitleaks pre-commit hook is configured, deliberately: the upstream hook is declared
  `language: golang`, so it would make `pre-commit run --all-files` unrunnable on a machine
  without a Go toolchain.
- Data privacy rule recorded: no real patient or personally identifiable health data may
  ever be committed, per the Data Privacy Act of 2012 (RA 10173). See
  [`docs/DATA.md`](docs/DATA.md).

[Unreleased]: https://github.com/andrewhmir/gengineer-pjdsc-2026/commits/main
[0.1.0]: https://github.com/andrewhmir/gengineer-pjdsc-2026/tags
