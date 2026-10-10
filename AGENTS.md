# AGENTS.md — repository-wide agent instructions

Scope: the whole repository. This file is the **fallback**: when you edit a file, the
closest `AGENTS.md` walking up the tree wins, so read the lane file first if one sits
beside your target. Lane files are listed in the lane map below.

This file is operational — commands, hard rules, and the environment quirks that look
like repository faults but are not. The reasoning behind the repository's shape is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), and it is not repeated here.

## What this repository is

A public health analytics entry for the **Philippine Junior Data Science Challenge
(PJDSC) 2026**, integrating a CircuitPython sensor node with a web application. It is a
**judged** submission: the repository itself is scored on code structure and
documentation, functional execution and reproducibility, and dependencies and data
management, so tidiness is worth points.

One history, three lanes: **firmware** (`firmware/`), **data / analysis** (`data/` and
`notebooks/`), and **web** (`webapp/`). `tests/`, `docs/`, `specs/`, and `submission/`
are cross-cutting, not a fourth lane. Integration changes may touch several lanes in one
pull request, which must then name every lane it touches.

**There is no installable Python package here.** No `src/`, no build backend;
`pyproject.toml` sets `package = false` under `[tool.uv]`. That is a deliberate
decision, not an omission: do not add a `src/` tree, a build backend, or packaging
metadata to "help". Analysis code lives in notebooks and web code in `webapp/`; a shared
package is extracted only when a second real consumer of shared logic exists.

## Lane map

| Folder | Language / toolchain | Deploy model | Lane rules |
|---|---|---|---|
| `firmware/` | CircuitPython, running on the board | **Copied** wholesale to the board's `CIRCUITPY` USB drive | [`firmware/AGENTS.md`](firmware/AGENTS.md) |
| `data/`, `notebooks/` | Python 3.12 via `uv`, Jupyter | Runs on a laptop or CI, against committed samples | [`notebooks/AGENTS.md`](notebooks/AGENTS.md), [`docs/DATA.md`](docs/DATA.md) |
| `webapp/` | **Undecided** — no framework has been chosen | Served over HTTP | [`webapp/AGENTS.md`](webapp/AGENTS.md) |
| `tests/` | pytest, Python 3.12 via `uv` | Runs on a laptop or CI; no hardware, no network | [`tests/AGENTS.md`](tests/AGENTS.md) |

`data/raw/` and `data/interim/` hold local-only data and are gitignored.
`data/samples/` holds the small synthetic fixtures that are committed.

## Commands

Every Python command goes through `uv run`. Never call bare `python`, `pytest`, `ruff`,
or `mypy` — see *Known environment constraints* for why.

| Command | Purpose |
|---|---|
| `uv sync` | Create or update `.venv` from `uv.lock`. |
| `uv run pytest` | The full suite. It must pass from a clean clone, with no hardware attached and no network access. |
| `uv run pytest -v` | The suite, one line per test. |
| `uv run pytest tests/test_<name>.py -v` | One file. |
| `uv run ruff format .` | Format, writing changes. |
| `uv run ruff format --check .` | Verify formatting without writing. |
| `uv run ruff check .` | Lint. |
| `uv run mypy` | Type-check `tests/`. |
| `pre-commit run --all-files` | Configured, but **cannot run on this machine** — see below. |

The local gate before you push is these four commands:

```console
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

They mirror CI. There is no `Makefile`; the repository deliberately provides no task
runner beyond `uv` itself.

## Hard rules

- **Never commit directly to `main`.** Every change goes on a branch and lands through a
  pull request. Branch names, commit types, scopes, and the review flow:
  [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Never commit anything under `data/raw/` or `data/interim/`.** Structure is
  committed, contents are not.
- **Never commit `firmware/secrets.py` or `.env`.** Commit the templates
  `firmware/secrets.example.py` and `.env.example` instead.
- **Never commit real patient or personally identifiable health data.** Data Privacy Act
  of 2012 (RA 10173). Committed fixtures under `data/samples/` are synthetic and
  labelled as such.
- **Never edit anything under `firmware/lib/`.** It is vendored third-party code.
- **No AI attribution trailers**: no `Co-Authored-By`, no "Generated with" footer.
  Commits read as the human author's work.
- **Conventional Commits.** Use a lane scope when the change belongs to one lane
  (`feat(firmware): …`, `feat(data): …`); use an unscoped type for cross-cutting or
  root-level work that belongs to no single lane (`chore:`, `ci:`, `test:`, `docs:`).
  Details: [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **English only** — code, comments, notebook prose, commit messages, and issues.
- Do not commit `.superpowers/` or `.worktrees/`; they are agent working artifacts.
- Do not edit `specs/`. Those are frozen, controller-owned design records.
- Do not add a `.gitkeep`; a directory that needs to exist gets a `README.md` that
  carries real guidance.

## Where to look instead of duplicating

These files are the single source of truth for their subject. Link to them; do not
restate them here or in a lane file.

| Question | File |
|---|---|
| How do I branch, commit, open a pull request, add a teammate? | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| What may be committed, and how is the real dataset obtained? | [`docs/DATA.md`](docs/DATA.md) |
| Where must every dataset and source be cited? | [`docs/SOURCES.md`](docs/SOURCES.md) — APA 7th Edition |
| Why is the repository shaped this way, and where are the lane boundaries? | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Secret handling and vulnerability reporting | [`SECURITY.md`](SECURITY.md) |
| Owner-level setup: ruleset, labels, approvals | [`docs/SETUP.md`](docs/SETUP.md) |
| What actually exists today? | [`CHANGELOG.md`](CHANGELOG.md) |

A rule that belongs to one lane belongs in that lane's `AGENTS.md`, not here.

## Known environment constraints

Each item below is a property of the **maintainer's machine**, not a repository defect.
Do not "fix" the repository to work around one of them.

1. **`pre-commit run --all-files` cannot create its hook environments here.**
   `virtualenv` fails on its out-of-repo cache with
   `PermissionError: [WinError 5] Access is denied`, and without an explicit `TMPDIR` it
   fails with `FileNotFoundError: No usable temporary directory found`.
   `.pre-commit-config.yaml` is **correct as committed** — do not change, weaken, or
   disable it to make the hook run. The four commands under *Commands* are the
   equivalent gates.
2. **Bare `python` on PATH is 3.10.11, while `uv run` resolves 3.12.0** via
   `.python-version`. A bare `python -m pytest` fails the version-floor assertion in
   `tests/test_repo_smoke.py` for that reason alone. Every test and tool command must go
   through `uv run`.
3. **`gh auth switch` writes outside the repository**, to
   `%APPDATA%\GitHub CLI\hosts.yml`, and fails under a confined file sandbox. The active
   `gh` account on this machine is `andrew-aira`, while this repository's owner is
   `andrewhmir`, so `gh auth switch --user andrewhmir` is required before pushing. This
   is an account mix-up, not an access problem — `gh auth status` shows which account is
   active.
4. **Only Windows PowerShell 5.1 is installed; `pwsh` does not exist.** A command
   written as `pwsh -Command …` fails with `CommandNotFoundException`; use `powershell`.
   In PowerShell the backtick is the escape character, so a double-quoted regex that
   contains backticks is silently altered — single-quote it instead.
5. **`git` here has `core.autocrlf=true`.** `.gitattributes` is what pins LF in the
   index; do not remove or override it. If `.gitattributes` is not present yet, the
   bootstrap has simply not reached the CI task that adds it.
6. **There is deliberately no gitleaks pre-commit hook.** The upstream hook needs a Go
   toolchain, and `gitleaks/gitleaks-action` is license-gated, so secret scanning runs in
   CI instead: the `secrets` job installs and runs the gitleaks CLI
   (`gitleaks detect --config .gitleaks.toml --redact -v`). Do not write guidance that
   implies a local gitleaks hook exists.

## Lane reminders

- **`firmware/`** is copied onto a `CIRCUITPY` drive, never imports from the repository
  root, keeps hardware behind an injectable seam, and treats everything in
  `firmware/lib/` as read-only vendored code. CI can only prove the firmware
  byte-compiles; a human must flash it. Details: [`firmware/AGENTS.md`](firmware/AGENTS.md).
- **`webapp/`** has **no framework chosen and no framework decision made**. Do not
  scaffold a framework, add dependencies, or restructure the repository for a web app
  until a human chooses one. Details: [`webapp/AGENTS.md`](webapp/AGENTS.md).
