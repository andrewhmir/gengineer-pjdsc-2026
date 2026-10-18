# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Repository history is Conventional Commits with a lane scope; this file is the
human-readable summary a judge or a returning teammate can read without walking the log.

## [Unreleased]

### Added

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
- Research records committed under `notebooks/research/`: the all-in-one Pa-Hinga
  (`CSI-YASAT`) master v2.1 and the Resonance Network study on the High-Gamma Dataset
  (`D01_10-17_Gengineer.ipynb`), with outputs stripped. They need a GPU and external
  datasets, which the locked root environment deliberately does not install, so the
  `notebooks` CI job excludes that one directory by path (`--ignore=notebooks/research`)
  rather than executing it; the lane `README.md` and `notebooks/research/README.md` state
  the rule and the reason, and a test pins both halves of the command. The three datasets
  the records use — the MIMIC-III Waveform Database, CSI-Bench, and the High-Gamma Dataset —
  with their descriptor and platform citations, are recorded in `docs/SOURCES.md`. No data
  is committed.

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
