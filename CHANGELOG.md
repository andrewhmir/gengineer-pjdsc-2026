# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Repository history is Conventional Commits with a lane scope; this file is the
human-readable summary a judge or a returning teammate can read without walking the log.

## [Unreleased]

### Added

- **Universal firmware 1.2.0**: versions now have three parts, MAJOR.MINOR.PATCH, as in the review branch
  `fix/universal-firmware-v2`, whose two fixes this version carries: the node's address is set before Wi-Fi starts,
  and the receiver's `rx_state` column carries `rx_state` instead of repeating `sig_mode`.
- **Universal firmware 1.1**: the transmitter prints a `HINIGRAM_TX` line with its version, ID, addresses, build
  and radio settings, and each release's `build-info.json` records the settings of both images, so the console can
  compare what a board runs with what it could write. What the boards send is unchanged.
- **Firmware releases built on GitHub**: `.github/workflows/firmware-release.yml` compiles the universal
  firmware (transmitter and receiver) with ESP-IDF 5.3.2 on every push that changes it, and publishes each new
  version as the release `universal-v<version>` with both images, their SHA-256 sums and a `build-info.json`.
  The version is `firmware/hinigram_universal_node/version.txt` and every version has an entry in that folder's
  `CHANGELOG.md`; a code change without a new version fails the workflow, so a published version never changes.
- **Universal transmitter firmware** `firmware/hinigram_universal_node/` 1.0 (ESP-IDF 5.1+, original
  ESP32; branch `firmware/universal-node`): one image for any number of chair nodes. The node ID (1 to
  254) lives in the board's NVS flash, not in the build, and is set or changed over USB serial with
  `hinigram id N` without writing the firmware again; `hinigram info` repeats the start-up lines, which
  give the version, the chip address and whether the ID is stored. Radio settings, timing and packet are
  those of the v1.3.3 bundle's `hinigram_node`: 20 MHz, MCS0, 30 packets a second from
  `1a:00:00:00:00:<ID>`, a steady period with up to 2 ms of random offset. Compiled with ESP-IDF 5.3.2;
  not yet run on a board.
- `firmware/hinigram_receiver/`, the v1.3.3 bundle's corner receiver copied unchanged so it is under
  version control next to the universal node. It accepts nodes 1 to 254 (the team's `csi_rx` accepts
  1 to 3), writes through the UART driver with a 64-packet queue, and reports how many lines it logged
  and dropped every 60 s. One receiver at 921,600 baud carries about five nodes at 30 packets a second.
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
