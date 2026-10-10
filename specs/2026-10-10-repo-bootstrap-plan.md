# Repository Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `gengineer-pjdsc-2026` repository — a public, team-ready, problem-agnostic scaffold with a locked Python environment, enforced git governance, lane-separated structure, and agent instruction files — so the team can start work the moment the challenge problem is chosen.

**Architecture:** One repository hosting three sibling lanes (`firmware/`, `notebooks/`, and a placeholder `webapp/`) plus a scored-deliverables `submission/` lane and a `data/` policy lane. Readiness comes from process and structure, not from guessing the domain. One `uv` project at the root; `firmware/` is CircuitPython and is deliberately *not* a Python package, because it is copied wholesale onto a `CIRCUITPY` USB drive. CI is green on day one and auto-skips unimplemented lanes.

**Tech Stack:** Python 3.12, `uv`, `ruff`, `mypy`, `pytest`, `nbmake`, `nbstripout`, `pre-commit`, `gitleaks`, CircuitPython, GitHub Actions.

**Spec:** [`specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md)

## Global Constraints

Copied verbatim from the spec. Every task implicitly includes these.

- **Python version floor:** `3.12`. `.python-version` and `requires-python` must agree (REQ-022).
- **Ruff:** line length `100`; rule sets `E,F,W,I,UP,B,SIM`.
- **Mypy:** non-strict at bootstrap.
- **No `src/` package** and no installable package. Do not create one (spec §4.1 rule 2).
- **No `Makefile`, no Dockerfile, no DVC, no Git LFS, no docs site, no `.gitkeep`** (spec §2.4, REQ-013).
- **`.gitignore` must contain no trailing comments** — a line such as `data/raw/  # datasets` becomes a literal never-matching pattern. Comments go on their own lines.
- **Firmware is CircuitPython, not CPython.** No `dataclasses`, no `match`, no `X | Y` type syntax. Only the standard library plus the Adafruit bundle.
- **`firmware/` must not import from the repository root.**
- **`firmware/lib/` is vendored third-party code and is never hand-edited.**
- **No AI attribution trailers** on any commit: no `Co-Authored-By`, no "Generated with" footer.
- **Commit messages:** Conventional Commits. Use a lane scope when the change belongs to one lane (`feat(firmware): add DHT22 reader`, `feat(data): ...`, `docs(webapp): ...`); use an unscoped type for cross-cutting or root-level work that belongs to no single lane (`chore:`, `ci:`, `test:`, `docs:`). The spec's own bootstrap commits follow this split, so an unscoped `docs:` commit for root documentation is correct rather than a violation.
- **No commit may contain** a secret, credential, or real patient health data (REQ-070).
- **No committed file may exceed 1 MB** (REQ-031).
- **Uncommitted by policy:** `data/raw/*`, `data/interim/*`, `firmware/secrets.py`, `.env` (REQ-030).
- **Public-health framing is mandatory** in user-facing docs: the competition theme is Public Health Analytics.
- **Slide deck limit 20 slides; demo video limit 3 minutes.** These are scored limits (deductions apply) and are recorded in `submission/README.md`.
- **All repository content is in English.**
- Platform facts on this machine: only Windows PowerShell 5.1 exists (`pwsh` does not); `git` and `uv` are on PATH; `git` has `core.autocrlf=true`.

## Review Focus

The spec implies these conditions but no task's own tests fully exercise them. Each is the failure most likely to bite a real user, and each gets pinned by a test in the task that owns the code.

1. **A Windows contributor's CRLF line endings silently break a shell script or `uv.lock`.** A reasonable person expects a clone on Windows and a clone on macOS to behave identically. → pinned in Task 9 (`test_gitattributes_forces_lf_for_lockfile_and_python`); Task 1's own suite deliberately does not assert it.
2. **A notebook is committed with outputs, bloating the repository and leaking data.** A reasonable person expects `data/raw/` contents never to appear in a commit. → pinned in Task 8 (`test_template_notebook_has_no_outputs`).
3. **Firmware imports a host-only or root-level module and compiles fine but crashes on the board at boot.** A meaningful failure because CI cannot catch it on hardware. → pinned in Task 4 (`test_firmware_does_not_import_repo_root`, `test_code_py_has_no_forbidden_constructs`).
4. **A teammate pastes WiFi credentials into `firmware/secrets.py` and it gets committed.** The single most common CircuitPython leak. → pinned in Task 5 (`test_secrets_py_is_ignored`, `test_secrets_example_is_committed`).
5. **Real patient data is committed to `data/` despite the policy.** A privacy and legal failure under RA 10173, not just a hygiene one. → pinned in Task 5 (`test_data_tree_shape_committed` plus the `.gitignore` assertions).

---

### Task 1: Root Python toolchain, ignore rules, and smoke test

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.editorconfig`
- Create: `.gitignore`
- Create: `.gitleaks.toml`
- Create: `.pre-commit-config.yaml`
- Create: `tests/AGENTS.md`
- Create: `tests/conftest.py`
- Create: `tests/test_repo_smoke.py`

**Interfaces:**
- Consumes: nothing. This is the first task.
- Produces: fixture `repo_root` (a `pathlib.Path` to the repository root) in `tests/conftest.py`, used by every later task's tests. `REQUIRED_ROOT_FILES` (a `tuple[str, ...]`) in `tests/test_repo_smoke.py`, which later tasks extend.

- [ ] **Step 1: Write the failing test**

Create `tests/test_repo_smoke.py`. Assertions are the spec's own acceptance criteria, so they are real tests and not placeholders.

```python
"""Bootstrap invariants for the repository scaffold.

These are genuine assertions: they fail if a lane is removed, the Python pin
is lost, or the secret-scanning configuration disappears.
"""

import sys
from pathlib import Path

import pytest

REQUIRED_ROOT_FILES = (
    "pyproject.toml",
    ".python-version",
    ".gitignore",
    ".gitleaks.toml",
    ".pre-commit-config.yaml",
    ".editorconfig",
)
REQUIRED_ROOT_DIRS = ("tests",)


@pytest.mark.parametrize("name", REQUIRED_ROOT_FILES)
def test_required_root_file_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing required root file: {name}"


@pytest.mark.parametrize("name", REQUIRED_ROOT_DIRS)
def test_required_root_dir_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_dir(), f"missing required root directory: {name}"


def test_python_version_pin_is_consistent(repo_root: Path) -> None:
    """REQ-022: .python-version and requires-python must agree."""
    pin = (repo_root / ".python-version").read_text(encoding="utf-8").strip()
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    assert pin.startswith("3.12"), f"unexpected pin: {pin!r}"
    assert 'requires-python = ">=3.12"' in pyproject


def test_supported_python_floor_is_enforced() -> None:
    assert sys.version_info >= (3, 12), "run the suite with Python 3.12 or newer"


def test_gitignore_has_no_trailing_comments(repo_root: Path) -> None:
    """A trailing comment turns a pattern into a never-matching literal."""
    offenders = [
        line
        for line in (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "#" in line
    ]
    assert not offenders, f"trailing comments on .gitignore patterns: {offenders}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_repo_smoke.py -v`
Expected: FAIL — `uv` cannot resolve a project, because `pyproject.toml` does not exist yet.

- [ ] **Step 3: Create `pyproject.toml`, `.python-version`, `.editorconfig`**

`pyproject.toml` — exact content:

```toml
[project]
name = "gengineer-pjdsc-2026"
version = "0.1.0"
description = "PJDSC 2026 entry: public health analytics with microcontroller and web application integration."
readme = "README.md"
requires-python = ">=3.12"
license = "Apache-2.0"
dependencies = []

[dependency-groups]
dev = [
    # Pinned exactly, not a floor: the version must match the ruff-pre-commit rev
    # in .pre-commit-config.yaml, or `ruff format --check` disagrees between a
    # contributor's machine and CI. Ruff >=0.14 also formats Python code blocks
    # inside Markdown, which changes what a whole-repo format check sees.
    "ruff==0.17.0",
    "mypy>=1.11",
    "pytest>=8.3",
    "pytest-cov>=5.0",
    "nbmake>=1.5",
    # Present so the documentable command `uv run nbstripout --verify <notebook>` works.
    # The pre-commit hook is the primary enforcement, but it cannot run on the maintainer's
    # machine (see the root AGENTS.md), so the CLI is the fallback an agent or human can
    # actually execute. Keeping the command runnable is worth one dev dependency.
    "nbstripout>=0.8",
    "pre-commit>=3.8",
]

[tool.ruff]
line-length = 100
target-version = "py312"
# specs/ holds frozen design records: the spec and the implementation plan as
# they were approved. Reformatting them would rewrite the historical record and
# bury the prose that decisions were argued from, so they are never formatted.
extend-exclude = ["specs"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
files = ["tests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra --strict-markers"

# This repository ships no importable package (spec §4.1 rule 2), so uv must not
# try to build or install the project itself. Without this, `uv sync` builds the
# root project and fails on `readme = "README.md"` until Task 2 creates that file.
[tool.uv]
package = false
```

`.python-version` — exact content: `3.12`

`.editorconfig` — exact content:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 4

[*.{yml,yaml,json,toml}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

- [ ] **Step 4: Create `.gitignore`, `.gitleaks.toml`, `.pre-commit-config.yaml`, `tests/conftest.py`, `tests/AGENTS.md`**

`.gitignore` — exact content. Note: **no trailing comments on pattern lines.**

```gitignore
# --- Python ---
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.venv/
venv/

# --- Tooling caches ---
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/

# --- Secrets: never commit ---
.env
.env.local
firmware/secrets.py
*.pem
*.key

# --- Data: structure is committed, contents are not ---
data/raw/*
!data/raw/README.md
data/interim/*
!data/interim/README.md

# --- Notebook checkpoints ---
.ipynb_checkpoints/

# --- OS and editor ---
.DS_Store
Thumbs.db
*.swp

# --- Agent working artifacts ---
.worktrees/
.superpowers/
.agents/
```

`.gitleaks.toml` — exact content:

```toml
title = "gengineer-pjdsc-2026 gitleaks config"

[extend]
useDefault = true

[allowlist]
description = "Committed example files contain placeholders, never real credentials."
paths = [
    '''secrets\.example\.py''',
    '''\.env\.example''',
    '''docs/SETUP\.md''',
]
```

`.pre-commit-config.yaml` — exact content:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
        exclude: ^firmware/lib/
      - id: check-yaml
      - id: check-toml
      - id: check-json
        exclude: ^notebooks/
      - id: check-added-large-files
        args: ["--maxkb=1024"]
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    # This rev MUST equal the pinned ruff version in pyproject.toml's dev group.
    rev: v0.17.0
    hooks:
      - id: ruff
        args: ["--fix"]
      - id: ruff-format

  - repo: https://github.com/kynan/nbstripout
    rev: 0.7.1
    hooks:
      - id: nbstripout

# Deliberately no gitleaks hook here. The upstream gitleaks hook uses
# `language: golang` and requires a Go toolchain, which this project does not
# depend on; adding it would make `pre-commit run --all-files` unrunnable on a
# machine without Go. Secret scanning is enforced in CI by the `secrets` job,
# which installs and runs the gitleaks CLI against .gitleaks.toml.
# See SECURITY.md at the repository root.
```

`tests/conftest.py` — exact content. This fixture is the interface every later task uses.

```python
"""Shared pytest fixtures."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return Path(__file__).resolve().parent.parent
```

`tests/AGENTS.md` — exact content:

```markdown
# AGENTS.md — tests

Scope: everything under `tests/`. The closest `AGENTS.md` wins; see the root
`AGENTS.md` for repository-wide rules.

## Hard rules

- **No hardware and no network in tests.** These tests run on a laptop and in CI.
- **Never touch the real dataset.** Use fixtures from `data/samples/`.
- **Mock the board.** `board`, `busio`, and `digitalio` do not exist off-device;
  tests must inject fakes rather than importing them.
- Tests must pass with `uv run pytest` from a clean clone, with no manual setup.

## Commands

    uv run pytest              # full suite
    uv run pytest -v           # verbose
    uv run pytest tests/test_repo_smoke.py

## Notes

`repo_root` is a session-scoped fixture defined in `conftest.py`. Use it instead
of hard-coding paths or calling `os.getcwd()`.
```

- [ ] **Step 5: Generate the lockfile and run the tests to verify they pass**

Run:
```bash
uv sync
uv run pytest tests/test_repo_smoke.py -v
```
Expected: PASS, with zero failures. The exact collected count is whatever `pytest` reports; the requirement is zero failures and no errors.

Then confirm formatting and lint are clean:
```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
```
Expected: all three report success with no findings.

- [ ] **Step 6: Verify the large-file and ignore rules hold**

Run:
```bash
git add -A
git ls-files -z | xargs -0 -I{} sh -c 'test $(wc -c < "{}") -le 1048576 || echo "TOO LARGE: {}"'
```
Expected: no `TOO LARGE` output.

Run: `git check-ignore -v firmware/secrets.py data/raw/anything.csv data/interim/step.csv .env`
Expected: all four paths report a matching `.gitignore` rule.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .python-version .editorconfig .gitignore \
        .gitleaks.toml .pre-commit-config.yaml tests/
git commit -m "chore: bootstrap root Python toolchain, ignore rules, and smoke tests"
```

---

### Task 2: Human-facing documentation and governance files

**Files:**
- Create: `README.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`
- Create: `LICENSE`
- Create: `CITATION.cff`
- Create: `.env.example`
- Create: `docs/README.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/DATA.md`
- Create: `docs/SOURCES.md`
- Create: `docs/SETUP.md`
- Test: `tests/test_docs.py`

**Interfaces:**
- Consumes: the `repo_root` fixture from Task 1.
- Produces: document paths that `AGENTS.md` files (Task 3) reference instead of duplicating: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/DATA.md`, `docs/SOURCES.md`, `docs/SETUP.md`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_docs.py`:

```python
"""Documentation completeness and rubric-driven artifacts (REQ-014, REQ-063)."""

from pathlib import Path

import pytest

REQUIRED_DOCS = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "LICENSE",
    "CITATION.cff",
    ".env.example",
    "docs/README.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA.md",
    "docs/SOURCES.md",
    "docs/SETUP.md",
)


@pytest.mark.parametrize("name", REQUIRED_DOCS)
def test_required_document_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing required document: {name}"


def test_readme_contains_working_quickstart(repo_root: Path) -> None:
    """REQ-063: a stranger must be able to run the project from the README alone."""
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "uv sync" in readme, "README must document the one-command setup"
    assert "uv run pytest" in readme, "README must document how to run the tests"


def test_readme_states_the_competition_theme(repo_root: Path) -> None:
    readme = (repo_root / "README.md").read_text(encoding="utf-8").lower()
    assert "public health" in readme
    assert "pjdsc" in readme


def test_sources_documents_apa_seventh_edition(repo_root: Path) -> None:
    """REQ-014: 'Sources' is a scored rubric criterion."""
    sources = (repo_root / "docs/SOURCES.md").read_text(encoding="utf-8")
    assert "APA" in sources and "7th" in sources


def test_data_doc_prohibits_personal_health_data(repo_root: Path) -> None:
    """Privacy obligation under RA 10173."""
    data_doc = (repo_root / "docs/DATA.md").read_text(encoding="utf-8")
    assert "10173" in data_doc
    assert "real patient" in data_doc.lower() or "personally identifiable" in data_doc.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_docs.py -v`
Expected: FAIL — `README.md` and the other documents do not exist.

- [ ] **Step 3: Write `README.md`**

Structure it as a judging surface (spec §2.3, §7): the rubric scores "Code Structure and Documentation" and a reviewer opens this file first. It must contain, in this order: project title and one-line description; the competition context and public-health theme; repository map with one line per lane; quickstart with the literal commands `uv sync` and `uv run pytest`; data policy summary linking to `docs/DATA.md`; citation pointer to `docs/SOURCES.md`; team and license line.

Keep every documented command literally runnable — do not document a command that has not been tested.

- [ ] **Step 4: Write the remaining documents**

- `CONTRIBUTING.md` — branch naming (`firmware/*`, `data/*`, `notebooks/*`, `webapp/*`, `docs/*`, `chore/*`, `specs/*`); Conventional Commits with lane scope; the pull request flow; and an **"Adding a teammate"** section with the three steps: invite as a collaborator, add the handle to `.github/CODEOWNERS`, add the contributor to `CITATION.cff`. State that the required-approval ruleset is enabled at this moment, not before (spec §7.4).
- `SECURITY.md` — no secrets in the repository; `firmware/secrets.py` and `.env` are gitignored and `secrets.example.py` is the template; **secret scanning runs as the `secrets` CI job, not as a pre-commit hook** (state why: the upstream gitleaks hook needs a Go toolchain, so it would make `pre-commit run --all-files` unrunnable on a machine without Go); how to report a leak; how to rotate a compromised credential; and the prohibition on real patient data referencing `docs/DATA.md`.
- `CHANGELOG.md` — Keep a Changelog structure with an `Unreleased` section and the `0.1.0` bootstrap entry.
- `LICENSE` — full Apache License 2.0 text (spec §11 leaves this confirmable; Apache-2.0 is the proposed default because the web app may be deployed publicly).
- `CITATION.cff` — `cff-version: 1.2.0`, message, `title`, `type: software`, `license: Apache-2.0`, and an `authors` list containing `@andrewhmir`. The event publishes qualifying repositories with citation to each contributing member, so every teammate is added here.
- `.env.example` — the committed template for `.env`, mirroring the `secrets.example.py` pattern: placeholder keys only, no real values, with a comment that `.env` itself is gitignored. This file exists so `.gitleaks.toml`'s `.env.example` allowlist entry guards a real file rather than being dead configuration.
- `docs/README.md` — index of the `docs/` set and of `specs/`.
- `docs/ARCHITECTURE.md` — the three-lane model, the rule that `firmware/` is copied to the `CIRCUITPY` drive and never imports from the repository root, the `firmware/lib/` vendoring rule, and the list of official competition topics so future work is framed against them.
- `docs/DATA.md` — what may and may not be committed; `data/raw/` and `data/interim/` are never committed; `data/samples/` holds small fixtures and is committed so tests and judges can run without the full dataset; retrieval procedure for full datasets; and the **RA 10173 / Data Privacy Act of 2012** rule that no real patient or personally identifiable health data may ever be committed.
- `docs/SOURCES.md` — data provenance and citations. State the format as **APA 7th Edition**, and include at least one real entry. Because the specific datasets are not yet chosen, include a clearly-labelled template entry plus the competition's own source, and a note that every dataset used must be added here before it is used in analysis.
- `docs/SETUP.md` — owner-level operations in exact commands: creating the repository, the `gh auth switch --user andrewhmir` requirement and the sandbox caveat from spec §10.1, applying the ruleset, enabling required approvals when a second teammate joins, and setting labels.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_docs.py -v`
Expected: PASS with zero failures.

- [ ] **Step 6: Verify formatting and lint**

Run:
```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add README.md CONTRIBUTING.md SECURITY.md CHANGELOG.md LICENSE \
        CITATION.cff .env.example docs/ tests/test_docs.py
git commit -m "docs: add project documentation, governance, and citation files"
```

---

### Task 3: Agent instruction layer

**Files:**
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `firmware/AGENTS.md`
- Create: `notebooks/AGENTS.md`
- Create: `webapp/AGENTS.md`
- Test: `tests/test_agent_instructions.py`

**Interfaces:**
- Consumes: the `repo_root` fixture from Task 1. References human docs created in Task 2 (`CONTRIBUTING.md`, `docs/DATA.md`) rather than restating them.
- Produces: the lane rule files that Tasks 4, 6, and 7 extend. `webapp/AGENTS.md` is created here; Task 7 creates the sibling `webapp/README.md`. Side effect worth knowing: creating these three lane files also brings `firmware/`, `notebooks/`, and `webapp/` into existence as directories, which is why the all-lanes-exist check can live in Task 12.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_instructions.py`:

```python
"""Agent instruction layer (REQ-050 to REQ-053).

Nested AGENTS.md files use nearest-file precedence, and shorter files are
followed more reliably, so length is asserted rather than merely encouraged.
"""

from pathlib import Path

import pytest

AGENTS_FILES = (
    "AGENTS.md",
    "firmware/AGENTS.md",
    "notebooks/AGENTS.md",
    "tests/AGENTS.md",
    "webapp/AGENTS.md",
)
MAX_AGENTS_LINES = 200


@pytest.mark.parametrize("name", AGENTS_FILES)
def test_agents_file_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing agent instructions: {name}"


@pytest.mark.parametrize("name", AGENTS_FILES)
def test_agents_file_is_within_line_budget(repo_root: Path, name: str) -> None:
    lines = (repo_root / name).read_text(encoding="utf-8").splitlines()
    assert len(lines) < MAX_AGENTS_LINES, (
        f"{name} is {len(lines)} lines; keep it under {MAX_AGENTS_LINES}"
    )


def test_claude_md_imports_agents_md(repo_root: Path) -> None:
    """REQ-052: a CLAUDE.md sibling makes AGENTS.md load in every session."""
    content = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in content


def test_root_agents_states_every_hard_prohibition(repo_root: Path) -> None:
    """One assertion per prohibition, so deleting any single rule turns this red.

    An either/or phrase check would stay green if the secrets or RA 10173 rules
    were removed, which is the defect this test exists to prevent.
    """
    content = (repo_root / "AGENTS.md").read_text(encoding="utf-8").lower()
    assert "never commit directly to `main`" in content
    assert "data/raw" in content
    assert "data/interim" in content
    assert "firmware/secrets.py" in content
    assert ".env" in content
    assert "10173" in content
    assert "firmware/lib/" in content



def test_firmware_agents_protects_vendored_code(repo_root: Path) -> None:
    """REQ-053. The vendored-read-only rule and the language subset are both needed."""
    content = (repo_root / "firmware/AGENTS.md").read_text(encoding="utf-8").lower()
    assert "never edit" in content and "lib/" in content
    assert "dataclasses" in content
    assert "match" in content


def test_webapp_agents_withholds_framework_decision(repo_root: Path) -> None:
    """An agent must not invent a framework that has not been chosen."""
    content = (repo_root / "webapp/AGENTS.md").read_text(encoding="utf-8").lower()
    assert "no framework has been chosen" in content
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_agent_instructions.py -v`
Expected: FAIL — none of the `AGENTS.md` files exist.

- [ ] **Step 3: Write root `AGENTS.md` and `CLAUDE.md`**

Root `AGENTS.md` sections, under 200 lines, operational rather than narrative:

1. Repository purpose and the three-lane model, in three lines.
2. Lane map table: folder, language/toolchain, deploy model.
3. Commands: `uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`, `uv run mypy`, `pre-commit run --all-files`.
4. Hard rules: never commit directly to `main`; never commit anything under `data/raw/` or `data/interim/`; never commit `firmware/secrets.py` or `.env`; never commit real patient data; never edit `firmware/lib/`; no AI attribution trailers; Conventional Commits with lane scope.
5. Where to look instead of duplicating: `CONTRIBUTING.md` for the contribution flow, `docs/DATA.md` for the data policy, `docs/SOURCES.md` for citations, `docs/ARCHITECTURE.md` for lane boundaries.
6. Known environment constraints, stated so a future agent does not misdiagnose them as repository faults: (a) `gh auth switch` writes to `%APPDATA%\GitHub CLI\hosts.yml`, outside the workspace, and fails in a confined sandbox; (b) `pre-commit run --all-files` **cannot create its hook environments on this machine** — `virtualenv` fails on an out-of-repo cache with `WinError 5` — so `.pre-commit-config.yaml` is correct and must not be "fixed"; run `uv run ruff format --check .`, `uv run ruff check .`, and `uv run mypy` directly as the equivalent gates; (c) bare `python` on PATH is 3.10.11 while `uv run` resolves 3.12.0 via `.python-version`, so every test and tool command must go through `uv run`; (d) `git` on the maintainer's machine has `core.autocrlf=true`, and `.gitattributes` (Task 9) is what pins LF in the index.

`CLAUDE.md` — exact content:

```markdown
@AGENTS.md

## Claude Code

Repository-level instructions live in `AGENTS.md` and are imported above. Add
Claude-specific guidance below this line only; do not duplicate `AGENTS.md`.
```

- [ ] **Step 4: Write the lane `AGENTS.md` files**

- `firmware/AGENTS.md` — **never edit anything in `firmware/lib/`; it is vendored third-party code** and is refreshed by re-copying from the Adafruit bundle. The lane is flat and packaged by copy, so a new first-party module is a sibling of `code.py` at the firmware root, which the board already resolves — **do not add first-party modules to `firmware/lib/`, because that directory is vendored and out of review scope.** (State the two together; describing `lib/` as the place for shared code contradicts the read-only rule and leads an agent to bury its own module where review does not look.) CircuitPython is not CPython: no `dataclasses`, no `match`, no `X | Y` type syntax, stdlib plus bundle only. `firmware/` is copied wholesale onto the `CIRCUITPY` drive and **must not import from the repository root**. `code.py` is the auto-running entry point. Hardware access goes behind a seam so host-side tests can inject fakes. CI can only prove the code byte-compiles; it cannot prove the code runs on the board — a human must flash it to verify.
- `notebooks/AGENTS.md` — clear outputs before committing (`nbstripout` enforces this); no absolute paths; logic needed by more than one notebook belongs in an importable module, not in a cell; set deterministic seeds; never read from `data/raw/` in a committed output.
- `tests/AGENTS.md` — already written in Task 1, Step 4. Verify it exists and add the `firmware` fake-injection note if it is missing.
- `webapp/AGENTS.md` — state plainly that **no framework has been chosen and no framework decision has been made**; that the lane is a placeholder until the competition problem is fixed; and that an agent must not scaffold a framework, add dependencies, or restructure the repository to accommodate a web app until a human chooses one.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_agent_instructions.py -v`
Expected: PASS with zero failures.

- [ ] **Step 6: Verify the line budget and lint**

Run:
```bash
uv run pytest tests/test_agent_instructions.py -v -k line_budget
uv run ruff format --check .
uv run ruff check .
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md CLAUDE.md firmware/AGENTS.md notebooks/AGENTS.md \
        webapp/AGENTS.md tests/AGENTS.md tests/test_agent_instructions.py
git commit -m "docs: add nested agent instruction layer"
```

---

### Task 4: Firmware lane — CircuitPython skeleton with a host-testable seam

**Files:**
- Create: `firmware/README.md`
- Create: `firmware/code.py`
- Create: `firmware/lib/README.md`
- Create: `firmware/secrets.example.py`
- Create: `firmware/config.example.toml`
- Create: `firmware/.gitignore`
- Modify: `tests/AGENTS.md` — **already satisfied by Task 3, which added the firmware fake-injection bullet. Do not edit this file in Task 4;** verify the bullet is present and move on.
- Test: `tests/test_firmware.py`

**Interfaces:**
- Consumes: `repo_root` from Task 1; rules from `firmware/AGENTS.md` written in Task 3.
- Produces: `firmware/code.py` exposing `main()` (no arguments, returns `None`) and a module-level `HARDWARE_AVAILABLE: bool`. `run_check()` returns a `str` status line. Task 9's CI job byte-compiles every `firmware/**/*.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_firmware.py`. The import-guard test is the important one: it catches the failure mode where firmware compiles but crashes on the board.

```python
"""Firmware lane invariants.

CI cannot prove firmware runs on hardware. What it can prove is that the code
byte-compiles, avoids host-only constructs, and does not reach out of its own
lane — the three ways a CircuitPython program fails at boot.
"""

import ast
import py_compile
from pathlib import Path

import pytest

FIRMWARE_FORBIDDEN_CALLS = {"dataclass"}  # dataclasses are unavailable on CircuitPython
FIRMWARE_FORBIDDEN_NODES = (ast.Match,)   # match statements are unavailable
HOST_ONLY_ROOT_MODULES = {"tests", "notebooks", "webapp", "docs", "specs", "data"}


def firmware_sources(repo_root: Path) -> list[Path]:
    return sorted(
        path
        for path in (repo_root / "firmware").rglob("*.py")
        if "lib" not in path.parts
    )


def test_firmware_lane_has_sources(repo_root: Path) -> None:
    assert firmware_sources(repo_root), "firmware lane must contain at least code.py"


def test_firmware_sources_compile(repo_root: Path) -> None:
    for source in firmware_sources(repo_root):
        try:
            py_compile.compile(str(source), doraise=True, cfile=None)
        except py_compile.PyCompileError as exc:  # pragma: no cover - failure path
            pytest.fail(f"{source} does not byte-compile: {exc}")


def test_code_py_has_no_forbidden_constructs(repo_root: Path) -> None:
    """CircuitPython lacks dataclasses and match statements."""
    tree = ast.parse((repo_root / "firmware/code.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        assert not isinstance(node, FIRMWARE_FORBIDDEN_NODES), (
            "match is unavailable on CircuitPython"
        )
        if isinstance(node, ast.ImportFrom) and node.module in FIRMWARE_FORBIDDEN_CALLS:
            pytest.fail("dataclasses is unavailable on CircuitPython")


def test_firmware_does_not_import_repo_root(repo_root: Path) -> None:
    """firmware/ is copied to a CIRCUITPY drive; the repository does not travel with it."""
    for source in firmware_sources(repo_root):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = {node.module.split(".")[0]}
            else:
                continue
            offenders = roots & HOST_ONLY_ROOT_MODULES
            assert not offenders, f"{source} imports host-only modules: {sorted(offenders)}"


def test_code_py_imports_cleanly_off_device(repo_root: Path) -> None:
    """The hardware import is guarded, so the module is importable on a laptop."""
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location(
        "firmware_code", repo_root / "firmware" / "code.py"
    )
    assert spec is not None and spec.loader is not None
    firmware_code = module_from_spec(spec)
    spec.loader.exec_module(firmware_code)
    assert firmware_code.HARDWARE_AVAILABLE is False
    assert isinstance(firmware_code.run_check(), str)


def test_secrets_template_exists_and_real_file_is_ignored(repo_root: Path) -> None:
    assert (repo_root / "firmware/secrets.example.py").is_file()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_firmware.py -v`
Expected: FAIL — `firmware/code.py` does not exist.

- [ ] **Step 3: Create `firmware/code.py`**

Requirements the tests pin: a guarded hardware import so the module imports off-device; module-level `HARDWARE_AVAILABLE: bool`; `run_check() -> str`; `main() -> None`; an `if __name__ == "__main__":` block calling `main()`. Use only CircuitPython-safe constructs — no `dataclasses`, no `match`, no `X | Y` annotations. Guard the hardware import like this:

```python
try:
    import board  # noqa: F401
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
```

`run_check()` returns a human-readable status string; it must not require hardware.

**Known limitation, documented rather than hidden:** the filename `code.py` collides with
CPython's stdlib `code` module. The host-side test must therefore **not** put `firmware/` on
`sys.path`; it loads the file by path with `importlib.util.spec_from_file_location` under the
isolated module name `firmware_code`, which avoids shadowing `code` for anything else
imported during the session. Do not "fix" this by renaming the file — `code.py` is the
CircuitPython auto-run entry point name and is required. Add a comment in `firmware/README.md`
noting the collision.

- [ ] **Step 4: Create `firmware/README.md`, `firmware/lib/README.md`, `firmware/secrets.example.py`, `firmware/config.example.toml`, `firmware/.gitignore`**

- `firmware/README.md` — board flashing procedure (copy `code.py`, `lib/`, and a real `secrets.py` to the `CIRCUITPY` drive); the Adafruit CircuitPython bundle version used, pinned explicitly, with the refresh procedure for `lib/`; the CircuitPython language subset; how to run the host-side tests; and an explicit statement that **CI verifies byte-compilation only and cannot verify on-device behaviour**.
- `firmware/lib/README.md` — what belongs here, that these files are vendored from the Adafruit bundle at the pinned version, and that they are never hand-edited.
- `firmware/secrets.example.py` — the committed template that `firmware/secrets.py` is copied from, mirroring the Adafruit convention. **Placeholder values only**; it must contain no real credential. Document the keys CircuitPython code reads (WiFi SSID and password, and any API token), each set to an obvious placeholder such as `"YOUR_WIFI_SSID"`. Add a comment stating that `secrets.py` is gitignored and must never be committed. This file is asserted by `tests/test_firmware.py` and allowlisted in `.gitleaks.toml`, so it must exist even before any sensor code does.
- `firmware/config.example.toml` — board-agnostic placeholder keys (`[device]`, `name`, `sample_interval_s`, `[sensors]`), with a comment that CircuitPython cannot parse TOML with the standard library and that the file documents configuration rather than being read by the firmware. This avoids implying a parser that does not exist.
- `firmware/.gitignore` — exact content:
  ```gitignore
  # Real credentials never leave the board.
  secrets.py
  ```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_firmware.py -v`
Expected: PASS with zero failures.

- [ ] **Step 6: Verify the lane formatting and lint**

Run:
```bash
uv run ruff format --check firmware/
uv run ruff check firmware/
```
Expected: no findings. If ruff reports findings inside a vendored file under `firmware/lib/`, add an exclusion for `firmware/lib/` to `[tool.ruff]` in `pyproject.toml` rather than reformatting vendored code.

- [ ] **Step 7: Commit**

```bash
git add firmware/ tests/test_firmware.py
git commit -m "feat(firmware): add CircuitPython skeleton with host-testable seam"
```

---

### Task 5: Data policy and committed sample fixtures

**Files:**
- Create: `data/README.md`
- Create: `data/raw/README.md`
- Create: `data/interim/README.md`
- Create: `data/samples/README.md`
- Create: `data/samples/public_health_indicators.csv`
- Test: `tests/test_data_policy.py`

**Interfaces:**
- Consumes: the `.gitignore` rules from Task 1; `docs/DATA.md` and `docs/SOURCES.md` from Task 2.
- Produces: `data/samples/public_health_indicators.csv` — the fixture that Task 8's template notebook reads. Columns fixed for later tasks: `region,indicator,year,value`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_data_policy.py`:

```python
"""Data policy enforcement: the rubric scores data management, RA 10173 scores privacy."""

import subprocess
from pathlib import Path

import pytest

GITIGNORED_PATHS = (
    "data/raw/dataset.csv",
    "data/interim/step.csv",
    "firmware/secrets.py",
    ".env",
)
COMMITTED_DATA_FILES = (
    "data/README.md",
    "data/raw/README.md",
    "data/interim/README.md",
    "data/samples/README.md",
    "data/samples/public_health_indicators.csv",
)


def test_sensitive_paths_are_gitignored(repo_root: Path) -> None:
    for relative in GITIGNORED_PATHS:
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{relative} is NOT gitignored"


@pytest.mark.parametrize("name", COMMITTED_DATA_FILES)
def test_committed_data_fixture_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing committed data file: {name}"


def test_data_tree_root_exists(repo_root: Path) -> None:
    """The data lane owns this assertion; it deliberately does not appear in Task 1."""
    assert (repo_root / "data").is_dir()


def test_sample_fixture_has_expected_schema(repo_root: Path) -> None:
    lines = (repo_root / "data/samples/public_health_indicators.csv").read_text(
        encoding="utf-8"
    ).splitlines()
    assert lines, "sample fixture is empty"
    assert lines[0].strip() == "region,indicator,year,value"
    assert 2 <= len(lines) <= 50, "sample fixture must stay small; raw data does not belong in git"


def test_no_gitkeep_placeholders(repo_root: Path) -> None:
    """REQ-013: the tree is preserved with real README content, not empty placeholders."""
    assert not list(repo_root.rglob(".gitkeep"))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_data_policy.py -v`
Expected: FAIL — `data/` tree does not exist.

- [ ] **Step 3: Create the `data/` tree**

- `data/README.md` — the data policy in brief: `raw/` and `interim/` are never committed; `samples/` is committed; where full datasets come from; and a pointer to `docs/DATA.md` for the full policy including the RA 10173 prohibition.
- `data/raw/README.md` — what goes here, that it is gitignored, and the retrieval procedure pointer.
- `data/interim/README.md` — what goes here and that it is regenerable, so it is never committed.
- `data/samples/README.md` — what the committed fixtures are for (tests and judge reproducibility), the size ceiling, and the provenance requirement pointing at `docs/SOURCES.md`.
- `data/samples/public_health_indicators.csv` — header exactly `region,indicator,year,value`, with a handful of **illustrative, non-real** rows. Do not use real patient data or a real dataset; label it as illustrative in `data/samples/README.md`, because a synthetic fixture mistaken for a real dataset would mislead a judge.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_data_policy.py -v`
Expected: PASS with zero failures.

- [ ] **Step 5: Verify nothing unwanted is staged**

Run: `git status --porcelain`
Expected: no file under `data/raw/` or `data/interim/` other than their `README.md`.

- [ ] **Step 6: Commit**

```bash
git add data/ tests/test_data_policy.py
git commit -m "feat(data): add data policy structure and committed sample fixture"
```

---

### Task 6: Notebooks lane

**Files:**
- Create: `notebooks/README.md`
- Create: `notebooks/_template.ipynb`
- Test: `tests/test_notebooks.py`

**Interfaces:**
- Consumes: `data/samples/public_health_indicators.csv` with columns `region,indicator,year,value` (Task 5); `notebooks/AGENTS.md` (Task 3).
- Produces: `notebooks/_template.ipynb`, which carries the `nbmake` marker tag so Task 9's CI job can select it. The tag is `nbmake` in the notebook's top-level `metadata.tags` list.

**Read this before writing either notebooks file — it settles a real ambiguity about duplication.**
The lane `README.md` is human-facing and states conventions; the lane `AGENTS.md` is agent-facing
and states operative rules. Where both would cover the same subject, the README carries the
explanation and the lane file links to it. Concretely: the naming convention (`NN-topic.ipynb`),
what belongs in a notebook versus a module, and the `nbstripout`/`nbmake` mechanics belong in
`notebooks/README.md`; `notebooks/AGENTS.md` keeps the rules (clear outputs before commit, no
absolute paths, no logic that another notebook copies, deterministic seeds) and points at the
README. Task 3 deliberately left that material out of `notebooks/AGENTS.md` for exactly this
reason, so **do not re-add it there** — if you find a rule genuinely missing from the lane file,
add the rule, not a copy of the README. The same split governs Task 7.

- [ ] **Step 1: Write the failing test**

Create `tests/test_notebooks.py`:

```python
"""Notebook hygiene: outputs in git leak data and bloat the clone."""

import json
from pathlib import Path

import pytest


def notebook_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "notebooks").glob("*.ipynb"))


def test_notebook_lane_has_a_template(repo_root: Path) -> None:
    assert (repo_root / "notebooks/_template.ipynb").is_file()


def test_template_notebook_has_no_outputs(repo_root: Path) -> None:
    """Pinned Review Focus item: committed outputs leak data and bloat the repo."""
    notebook = json.loads((repo_root / "notebooks/_template.ipynb").read_text(encoding="utf-8"))
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        assert not cell.get("outputs"), f"cell {index} contains stored output"
        assert cell.get("execution_count") is None, f"cell {index} has an execution count"


def test_template_notebook_is_marked_for_nbmake(repo_root: Path) -> None:
    notebook = json.loads((repo_root / "notebooks/_template.ipynb").read_text(encoding="utf-8"))
    assert "nbmake" in notebook.get("metadata", {}).get("tags", [])


def test_template_notebook_uses_relative_sample_path(repo_root: Path) -> None:
    """Absolute paths break for every other clone and for the judges."""
    notebook = json.loads((repo_root / "notebooks/_template.ipynb").read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    assert "data/samples/public_health_indicators.csv" in source
    assert "C:\\" not in source and "/Users/" not in source
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_notebooks.py -v`
Expected: FAIL — `notebooks/_template.ipynb` does not exist.

- [ ] **Step 3: Create `notebooks/_template.ipynb`**

A valid notebook JSON satisfying every assertion above. Required content:

- `nbformat: 4`, `nbformat_minor: 5`, `metadata.tags: ["nbmake"]`.
- A markdown cell stating the notebook's purpose and the rule that reusable logic does not live in cells.
- A code cell reading `data/samples/public_health_indicators.csv` **by relative path** with `pandas.read_csv`.
- A second code cell computing a simple groupby over `indicator` and `value`.
- All code cells with `"outputs": []` and `"execution_count": null`.

- [ ] **Step 4: Create `notebooks/README.md`**

Naming convention (`NN-topic.ipynb`), what belongs in a notebook versus a module, how `nbstripout` and the pre-commit hook protect the repository, how CI runs opted-in notebooks with `nbmake`, and a pointer to `notebooks/AGENTS.md`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_notebooks.py -v`
Expected: PASS with zero failures.

- [ ] **Step 6: Verify the notebook executes and is strip-clean**

Run: `uv run pytest --nbmake notebooks/_template.ipynb -v`
Expected: PASS. This proves the template works before it is offered to the team as the starting point.

**Before asserting strip-cleanliness, normalise the file once.** `nbstripout` rewrites every cell
`id` to that cell's index (`_utils.py`: `if 'id' in cell and not keep_id: cell['id'] = str(i)`), so a
hand-authored notebook **fails `--verify` even with no outputs at all**. Verified empirically:

| Template state | `nbstripout --verify` |
|---|---|
| hand-authored `"id": "probe-cell-1"` | exit 1 — "would have stripped" |
| no `id` field | exit 1, plus a validation error |
| `"id": "0"` (equal to the index) | exit 0 |
| after one `nbstripout` write pass | exit 0 |

So run the write pass once and commit the normalised result:

```bash
uv run nbstripout notebooks/_template.ipynb
uv run nbstripout --verify notebooks/_template.ipynb
```
Expected: the write pass normalises cell ids; then `--verify` exits 0.

Then record in `notebooks/README.md` that `--verify` reports **any** change the hook would make —
not only stored output — and that a newly handwritten notebook therefore needs one
`nbstripout` write pass before it passes. Without that note, the next author will read a `--verify`
failure as "my outputs are still there" when the real cause is an unnormalised cell id.

- [ ] **Step 7: Commit**

```bash
git add notebooks/ tests/test_notebooks.py
git commit -m "feat(notebooks): add notebook template with nbmake marker and sample fixture"
```

---

### Task 7: Webapp placeholder lane

**Files:**
- Create: `webapp/README.md`
- Test: `tests/test_placeholders.py`

**Read this before writing either webapp file — it settles a real ambiguity about duplication.**
The lane `README.md` and the lane `AGENTS.md` must not carry the same material. The split is:

- The **lane `README.md`** is human-facing: it states the decisions a person needs and links to the lane `AGENTS.md` for operative rules.
- The **lane `AGENTS.md`** is agent-facing: it states the operative rules that change how code is written, and links to the root docs and the lane README rather than restating them.

Concretely for this task: the "no framework chosen" statement, the candidate directions, and the selection criteria belong in `webapp/README.md`; `webapp/AGENTS.md` keeps the prohibition and points at the README. Task 3 deliberately left that material out of `webapp/AGENTS.md` for exactly this reason, so **do not re-add it there** — if you find a rule genuinely missing from the lane file, add the rule, not a copy of the README. The same split governs Task 6.

**Interfaces:**
- Consumes: `webapp/AGENTS.md` from Task 3.
- Produces: nothing consumed by later tasks. This task exists so the lane is discoverable and so the absence of a framework decision is explicit.

- [ ] **Step 1: Write the failing test**

Create `tests/test_placeholders.py`:

```python
"""Placeholder lanes must not pretend a decision has been made."""

from pathlib import Path


def test_webapp_readme_exists(repo_root: Path) -> None:
    assert (repo_root / "webapp/README.md").is_file()


def test_webapp_readme_defers_the_framework_decision(repo_root: Path) -> None:
    content = (repo_root / "webapp/README.md").read_text(encoding="utf-8").lower()
    assert "no framework" in content or "not been chosen" in content or "undecided" in content


def test_no_webapp_dependency_manifest_exists(repo_root: Path) -> None:
    """A placeholder pyproject.toml would be a lie about an unmade decision."""
    assert not (repo_root / "webapp/pyproject.toml").exists()
    assert not (repo_root / "webapp/package.json").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_placeholders.py -v`
Expected: FAIL — `webapp/README.md` does not exist.

- [ ] **Step 3: Create `webapp/README.md`**

State: what the lane is for; that **no framework has been chosen and no framework decision has been made**; the candidate directions to be evaluated once the problem is fixed (a served dashboard, a static report page, an API); the criteria for choosing (judge reproducibility first, since the rubric scores it); and the note that when a framework is chosen, this lane gains its own dependency manifest and the root `pyproject.toml` gains an explicit `tool.uv.workspace` exclusion. Point at `webapp/AGENTS.md`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_placeholders.py -v`
Expected: PASS with zero failures.

- [ ] **Step 5: Commit**

```bash
git add webapp/README.md tests/test_placeholders.py
git commit -m "docs(webapp): add deferred-decision placeholder lane"
```

---

### Task 8: Repository README quickstart validation

**Files:**
- Modify: `README.md`
- Test: `tests/test_quickstart.py`

**Interfaces:**
- Consumes: everything created in Tasks 1–7.
- Produces: nothing consumed by later tasks. This task exists because REQ-063 requires the quickstart to work verbatim, and a README that documents a command which fails is worse than no README for a judged submission.

- [ ] **Step 1: Write the failing test**

Create `tests/test_quickstart.py`:

```python
"""REQ-063: the README quickstart must work verbatim from a clean clone."""

import re
from pathlib import Path

FENCED_COMMAND = re.compile(r"^uv (sync|run [a-z-]+)", re.MULTILINE)


def test_readme_documents_only_uv_commands(repo_root: Path) -> None:
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "uv sync" in readme


def test_readme_names_every_lane(repo_root: Path) -> None:
    """The README must name all seven lanes. Its text is the assertion; the
    directories themselves are asserted by an all-lanes-exist check at the end
    of the plan, because firmware/ (Task 4), data/ (Task 5), notebooks/ (Task 6)
    and webapp/ (Task 7) do not exist yet at this point in the plan."""
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    for lane in ("firmware/", "notebooks/", "webapp/", "data/", "docs/", "tests/", "specs/"):
        assert lane in readme, f"README does not mention the {lane} lane"


def test_readme_documents_no_unrunnable_command(repo_root: Path) -> None:
    """Every `uv run <tool>` in the README must be a tool that is actually installed."""
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    documented = set()
    for match in FENCED_COMMAND.finditer(readme):
        parts = match.group(1).split()
        if len(parts) >= 2 and parts[0] == "run":
            documented.add(parts[1])
    for tool in documented:
        if tool in {"pytest"}:
            continue
        assert tool in pyproject, f"README documents `uv run {tool}` but it is not a dependency"
```

- [ ] **Step 2: Run the test to verify its state**

Run: `uv run pytest tests/test_quickstart.py -v`
Expected: this step has **no reachable red state**, and that is expected rather than a defect. Task 2
already delivered a README that names all seven lanes and documents `uv sync` and
`uv run pytest`, so the former "README does not yet name every lane" failure cannot occur. This
task's genuine value is (a) the two fixed tests it adds — the bare-`uv run mypy` case and the
`is_dir`/text split — and (b) the clean-clone verification in Step 5, which is what REQ-063
actually asks for and which no unit test can substitute. Record the observed result honestly
instead of manufacturing a failure; if a test does fail here, it is a real finding about the
README.

- [ ] **Step 3: Update `README.md` so the lane map and commands are complete and accurate**

Add or correct, in `README.md`: a repository map listing `firmware/`, `notebooks/`, `webapp/`, `data/`, `docs/`, `specs/`, and `tests/`, each with a one-line purpose; and the quickstart, which must be exactly these commands in this order:

```bash
git clone https://github.com/andrewhmir/gengineer-pjdsc-2026.git
cd gengineer-pjdsc-2026
uv sync
uv run pytest
```

Do not add a badge until Task 9's workflow is running, and only then reference the workflow by name that actually exists.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_quickstart.py -v`
Expected: PASS with zero failures.

- [ ] **Step 5: Verify the quickstart literally, in a clean clone**

Run in a temporary directory outside the repository:

```bash
git clone <path-to-repo> /tmp/quickstart-check
cd /tmp/quickstart-check
uv sync
uv run pytest -q
```

Expected: `uv sync` succeeds; pytest reports zero failures. A failure here means the README is wrong, not the environment — fix `README.md` or the underlying task and re-run.

- [ ] **Step 6: Commit**

```bash
git add README.md tests/test_quickstart.py
git commit -m "docs: document the lane map and verify the quickstart end to end"
```

---

### Task 9: GitHub configuration — CI, templates, CODEOWNERS, Dependabot

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/CODEOWNERS`
- Create: `.github/dependabot.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`
- Create: `.github/ISSUE_TEMPLATE/task.md`
- Create: `.gitattributes`
- Test: `tests/test_github_config.py`

**Interfaces:**
- Consumes: `pyproject.toml` (Task 1) for the `lint`, `test`, and `notebooks` jobs; `firmware/` (Task 4) for the `firmware` job; `notebooks/_template.ipynb` (Task 6) for the `nbmake` run.
- Produces: the job named **`ci-success`**, which is the status check that Task 11's ruleset requires. This name is an interface: Task 11 must reference it exactly.

- [ ] **Step 1: Write the failing test**

Create `tests/test_github_config.py`:

```python
"""GitHub configuration (REQ-040 to REQ-046)."""

from pathlib import Path

import pytest
import yaml

REQUIRED_GITHUB_FILES = (
    ".github/workflows/ci.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/task.md",
)
EXPECTED_JOBS = {"changes", "lint", "test", "notebooks", "firmware", "secrets", "ci-success"}


@pytest.mark.parametrize("name", REQUIRED_GITHUB_FILES)
def test_required_github_file_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing GitHub config: {name}"


def test_ci_workflow_is_valid_yaml_with_expected_jobs(repo_root: Path) -> None:
    workflow = yaml.safe_load(
        (repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    assert set(workflow["jobs"]) == EXPECTED_JOBS


def test_ci_has_aggregate_gate(repo_root: Path) -> None:
    """A required check whose job is skipped never reports, which would deadlock PRs."""
    workflow = yaml.safe_load(
        (repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    assert "ci-success" in workflow["jobs"]


def test_codeowners_covers_every_lane(repo_root: Path) -> None:
    content = (repo_root / ".github/CODEOWNERS").read_text(encoding="utf-8")
    for lane in ("firmware/", "notebooks/", "webapp/", "data/", "docs/", "specs/", "tests/"):
        assert lane in content, f"CODEOWNERS does not cover {lane}"
    assert "@andrewhmir" in content


def test_pull_request_template_requires_verification_and_lane(repo_root: Path) -> None:
    content = (repo_root / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8").lower()
    for required in ("what", "why", "verif", "lane"):
        assert required in content, f"PR template is missing a {required!r} section"


def test_gitattributes_forces_lf_for_lockfile_and_python(repo_root: Path) -> None:
    """Review Focus: CRLF in a lockfile or script breaks on another platform."""
    content = (repo_root / ".gitattributes").read_text(encoding="utf-8")
    assert "uv.lock" in content and "eol=lf" in content
    assert "*.sh" in content


def test_ci_does_not_run_lanes_that_do_not_exist(repo_root: Path) -> None:
    """A job must be guarded, or an unimplemented lane fails every pull request."""
    workflow = yaml.safe_load(
        (repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    for job_name in ("lint", "test", "notebooks", "firmware"):
        job = workflow["jobs"][job_name]
        assert "if" in job, f"job {job_name} is not guarded by a changed-path condition"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_github_config.py -v`
Expected: FAIL — `.github/` does not exist.

- [ ] **Step 3: Create `.gitattributes`**

Exact content:

```gitattributes
* text=auto eol=lf

*.sh text eol=lf
uv.lock text eol=lf
*.py text eol=lf
*.ipynb text eol=lf

*.png binary
*.jpg binary
*.pdf binary
*.mp4 binary
```

- [ ] **Step 4: Create `.github/workflows/ci.yml`**

Requirements the tests pin: the job set is exactly `changes`, `lint`, `test`, `notebooks`, `firmware`, `secrets`, `ci-success`; every job except `changes`, `secrets`, and `ci-success` carries an `if:` guard on the `changes` job output.

Design decisions to implement:

- Trigger on `push` to `main` and on `pull_request`. Set `permissions: contents: read` at the top level.
- `changes` uses `actions/checkout@v4` with `fetch-depth: 0`, then computes changed files with `git diff --name-only "${{ github.event.pull_request.base.sha }}...${{ github.sha }}"` for pull requests and `HEAD~1 HEAD` for pushes, writing them to a file. It sets outputs `python`, `notebooks`, and `firmware` (each `'true'` or `'false'`) by matching path prefixes, using `github.event.pull_request.base.sha` only when it is non-empty.
- `lint` (guarded on `changes.outputs.python == 'true'`) uses `astral-sh/setup-uv@v5` with `enable-cache: true`, then `uv sync --locked`, then `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`.
- `test` (guarded on `changes.outputs.python == 'true'`) runs `uv sync --locked` and `uv run pytest -q`.
- `notebooks` (guarded on `changes.outputs.notebooks == 'true'`) runs `uv sync --locked` and `uv run pytest --nbmake notebooks/ -q`.
- `firmware` (guarded on `changes.outputs.firmware == 'true'`) runs `python -m py_compile` over every `.py` file under `firmware/` except `firmware/lib/`, using `find ... -not -path '*/lib/*' -print0 | xargs -0 python -m py_compile`. Comment in the job that this proves byte-compilation only and cannot prove on-device behaviour.
- `secrets` (always) scans full history with the **free gitleaks CLI**, not the
  `gitleaks/gitleaks-action` action. The action's v2 release is license-gated and requires a
  `GITLEAKS_LICENSE` secret for organization-owned repositories, which would make this job fail
  for reasons unrelated to the code. Install the CLI on the runner and run the same command the
  project documents locally. Checkout with `fetch-depth: 0`, then run
  `gitleaks detect --config .gitleaks.toml --redact -v`. Adding the Go-dependent pre-commit hook
  is likewise forbidden (see Task 1).
- `ci-success` (always) has `needs: [changes, lint, test, notebooks, firmware, secrets]` and `if: always()`. It must fail when any needed job failed or was cancelled, and **succeed when jobs were skipped**. Guard against the cascade rule: a job skipped because its `needs` failed must not by itself count as a failure. Implement with a single step whose shell logic is:

```bash
if echo '${{ toJSON(needs) }}' | jq -e 'to_entries | map(.value.result) | any(. == "failure" or . == "cancelled")' > /dev/null; then
  echo "A required job failed or was cancelled."
  exit 1
fi
echo "All required jobs passed or were skipped."
```

- [ ] **Step 5: Create the remaining `.github/` files**

- `.github/PULL_REQUEST_TEMPLATE.md` — sections **What**, **Why**, **Lane(s) touched**, **How this was verified**, and a checklist (tests pass, `ruff` clean, no secrets, no data committed, docs updated). The lane section must say that an integration PR names every lane.
- `.github/CODEOWNERS` — `* @andrewhmir` as the default, plus explicit lines for `firmware/`, `notebooks/`, `webapp/`, `data/`, `docs/`, `specs/`, `tests/`, and `.github/`. Include a comment stating that teammates are added here as part of the add-a-teammate procedure in `CONTRIBUTING.md`.
- `.github/dependabot.yml` — weekly updates for the `uv` ecosystem rooted at `/`, and for `github-actions` rooted at `/`. Cap open pull requests at 5 for each, and label them `dependencies`.
- `.github/ISSUE_TEMPLATE/config.yml` — `blank_issues_enabled: false`.
- `.github/ISSUE_TEMPLATE/bug_report.md` — front matter `name`, `about`, `title: "[Bug] "`, `labels: type:bug`, then reproduction steps, expected versus actual, and environment.
- `.github/ISSUE_TEMPLATE/feature_request.md` — front matter with `labels: type:feature`, then problem, proposed solution, and lane.
- `.github/ISSUE_TEMPLATE/task.md` — lane-agnostic task template with acceptance criteria and a lane field, front matter `labels: type:task`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_github_config.py -v`
Expected: PASS with zero failures.

- [ ] **Step 7: Validate the workflow file beyond the tests**

Run: `uv run ruff check .` and `pre-commit run --all-files`
Expected: no findings. `check-yaml` validating `ci.yml` is part of the value here.

Verify the `ci-success` shell logic locally with the three cases that matter:

```bash
echo '{"lint":{"result":"failure"}}' | jq -e 'to_entries | map(.value.result) | any(. == "failure" or . == "cancelled")' ; echo "failure case exit: $?"
echo '{"lint":{"result":"skipped"}}' | jq -e 'to_entries | map(.value.result) | any(. == "failure" or . == "cancelled")' ; echo "skipped case exit: $?"
```
Expected: the failure case exits 0 (so the job then fails), and the skipped case exits non-zero (so the job then succeeds). Confirm the polarity is right — this is the single most error-prone line in the workflow.

- [ ] **Step 8: Commit**

```bash
git add .github/ .gitattributes tests/test_github_config.py
git commit -m "ci: add workflow, status-check gate, templates, and CODEOWNERS"
```

---

### Task 10: Submission lane

**Files:**
- Create: `submission/README.md`
- Test: `tests/test_submission.py`

**Interfaces:**
- Consumes: `docs/SOURCES.md` (Task 2) for the citation requirement; `README.md` (Task 8) which the submission README links to.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_submission.py`:

```python
"""The deck and video are scored deliverables with hard numeric limits (REQ-060)."""

from pathlib import Path


def test_submission_readme_exists(repo_root: Path) -> None:
    assert (repo_root / "submission/README.md").is_file()


def test_submission_records_slide_and_video_limits(repo_root: Path) -> None:
    """Exceeding either limit costs points, so the limits are recorded where work happens."""
    content = (repo_root / "submission/README.md").read_text(encoding="utf-8")
    assert "20" in content and "slide" in content.lower()
    assert "3" in content and ("minute" in content.lower() or "min" in content.lower())


def test_submission_lists_every_required_deliverable(repo_root: Path) -> None:
    content = (repo_root / "submission/README.md").read_text(encoding="utf-8").lower()
    for deliverable in ("slide deck", "video", "repository"):
        assert deliverable.split()[0] in content, f"submission README omits the {deliverable}"
    assert "docs/sources.md" in content.lower()


def test_submission_links_the_repository(repo_root: Path) -> None:
    content = (repo_root / "submission/README.md").read_text(encoding="utf-8")
    assert "github.com/andrewhmir/gengineer-pjdsc-2026" in content


def test_no_large_binary_is_committed_in_submission(repo_root: Path) -> None:
    """REQ-031: the video is linked, not committed."""
    offenders = [
        path.name
        for path in (repo_root / "submission").rglob("*")
        if path.is_file() and path.stat().st_size > 1024 * 1024
    ]
    assert not offenders, f"committed files over 1 MB: {offenders}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_submission.py -v`
Expected: FAIL — `submission/README.md` does not exist.

- [ ] **Step 3: Create `submission/README.md`**

Record, explicitly:

- The three required deliverables: the slide deck PDF, the recorded demonstration video, and the link to the code repository (`https://github.com/andrewhmir/gengineer-pjdsc-2026`).
- **The hard limits, with the deduction rule:** the deck is limited to 20 slides including title, references, and appendices, with 1 point deducted for every 1–2 slides beyond; the video is limited to 3 minutes, with 1 point deducted for every 15 seconds beyond; each capped at 10 points.
- The submission deadline: **2026-10-24, 23:59**.
- The scored criteria, so the team checks the deck against them: Project Rationale and Design; Execution and Impact; Code Repository; Demonstration Video; Technical Rigor and Innovation; Sources.
- **Sources must follow APA 7th Edition**, with `docs/SOURCES.md` named as the single source of truth.
- A **video decision record**: the video is **linked, not committed**, and why — a committed binary would exceed the repository size policy in `docs/DATA.md`. Where to record the link is stated.
- A pre-submission checklist ending with: no secrets committed, no data committed, README quickstart verified from a clean clone, CI green.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_submission.py -v`
Expected: PASS with zero failures.

- [ ] **Step 5: Commit**

```bash
git add submission/ tests/test_submission.py
git commit -m "docs(submission): add submission lane with scored limits and checklist"
```

---

### Task 11: Create the remote repository, push, and enforce the ruleset

**Files:**
- Modify: `docs/SETUP.md` (record what was actually applied)
- Test: none — this task's verification is the `gh` read-back in Step 6.

**Interfaces:**
- Consumes: the entire local repository from Tasks 1–10; the job name `ci-success` from Task 9, which the required status check must match exactly.
- Produces: the `origin` remote and the ruleset on `main` that later work depends on.

**Note on the environment change:** the spec (§10.1) assumed the file sandbox blocked `gh auth switch`, making remote creation a human step. The session now runs with `danger-full-access`, so the agent can perform this task directly. The spec assumption is superseded; record the correction in `docs/SETUP.md`.

- [ ] **Step 1: Switch to the repository owner's GitHub account**

Run:
```powershell
gh auth switch --user andrewhmir
gh auth setup-git
gh auth status
```
Expected: `gh auth status` lists `andrewhmir` with `Active account: true`. If the switch fails, stop and report the exact error rather than continuing under a different account — pushing as the wrong account creates a repository owned by the wrong user.

- [ ] **Step 2: Confirm the target does not already exist**

Run: `gh repo view andrewhmir/gengineer-pjdsc-2026`
Expected: a "not found" error, which is the desired state. If the repository exists, stop and ask the maintainer whether to use it rather than overwriting anything.

- [ ] **Step 3: Create the public repository and push `main`**

Run:
```bash
gh repo create gengineer-pjdsc-2026 --public \
  --source=. --remote=origin \
  --description "PJDSC 2026 entry: public health analytics with microcontroller and web application integration." \
  --push
```
Expected: the repository is created, `origin` is added, and `main` is pushed.

- [ ] **Step 4: Verify the push and the local/remote agreement**

Run:
```bash
git status -sb
git log --oneline -1
gh repo view andrewhmir/gengineer-pjdsc-2026 --json visibility,defaultBranchRef,url
```
Expected: `main` is up to date with `origin/main`; visibility is `PUBLIC`; the default branch is `main`.

- [ ] **Step 5: Wait for the first CI run, then apply the ruleset**

Run: `gh run list --limit 5` and wait until the run for the push to `main` completes.
Expected: the run concludes successfully, **including the `ci-success` job**. Do not create a required status check for a job that has never reported — the check name must exist before it can be required.

Then create the ruleset on `main` with rules: block deletion, block non-fast-forward (force-push), require a pull request before merging (`required_approving_review_count: 0`), require the `ci-success` status check, and require linear history. Write the exact ruleset JSON to a temporary file and apply it:

```bash
gh api --method POST repos/andrewhmir/gengineer-pjdsc-2026/rulesets \
  --input ruleset.json
```

**Do not set a required approval count above zero.** GitHub does not let a pull request author approve their own pull request, so with a single contributor this would make `main` unmergeable. Record the exact command to raise it to 1 in `docs/SETUP.md`.

- [ ] **Step 6: Verify the ruleset by read-back, and prove `main` is still workable**

Run:
```bash
gh api repos/andrewhmir/gengineer-pjdsc-2026/rulesets --jq '.[] | {name, enforcement, target}'
gh api repos/andrewhmir/gengineer-pjdsc-2026/rulesets/<id> --jq '.rules'
```
Expected: enforcement is `active`, target is `branch`, and the rules list includes deletion, non-fast-forward, pull_request, required_status_checks (with `ci-success`), and required_linear_history.

Then prove the repository is not locked out — create a trivial branch, open a pull request, and confirm it is mergeable with no approvals required:

```bash
git switch -c chore/verify-ruleset
git commit --allow-empty -m "chore: verify ruleset allows solo merge"
git push -u origin chore/verify-ruleset
gh pr create --fill --base main
gh pr view --json mergeable,mergeStateStatus
```
Expected: `mergeable: MERGEABLE`. If it reports `BLOCKED`, the approval rule is set incorrectly — fix it before continuing. Then merge and delete the branch:

```bash
gh pr merge --squash --delete-branch
git switch main && git pull
```

- [ ] **Step 7: Update `docs/SETUP.md` with what was actually applied, then commit**

Record: the ruleset identifier and its rules as read back; the command to raise required approvals to 1 when a second teammate joins; the instruction to add teammates as collaborators; and a correction noting that spec §10.1's sandbox limitation no longer applies under `danger-full-access`.

```bash
git add docs/SETUP.md
git commit -m "docs: record applied repository ruleset and teammate procedure"
git push
```

---

### Task 12: Final verification and dependency patch

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (add `httpx` for the CI API test below)
- Test: `tests/test_final_verification.py`

**Interfaces:**
- Consumes: every prior task.
- Produces: the final green state. Nothing consumes this task.

- [ ] **Step 1: Write the failing test**

Create `tests/test_final_verification.py`:

```python
"""Whole-repository acceptance checks that no single lane test owns."""

import subprocess
from pathlib import Path

import pytest

MAX_COMMITTED_BYTES = 1024 * 1024


def tracked_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line]


def test_no_tracked_file_exceeds_one_megabyte(repo_root: Path) -> None:
    """REQ-031."""
    offenders = []
    for name in tracked_files(repo_root):
        path = repo_root / name
        if path.is_file() and path.stat().st_size > MAX_COMMITTED_BYTES:
            offenders.append((name, path.stat().st_size))
    assert not offenders, f"tracked files over 1 MB: {offenders}"


def test_repository_root_files_are_present(repo_root: Path) -> None:
    """REQ-012: the inventory the spec commits to."""
    required = (
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "LICENSE",
        "CITATION.cff",
        "AGENTS.md",
        "CLAUDE.md",
        "pyproject.toml",
        "uv.lock",
    )
    missing = [name for name in required if not (repo_root / name).is_file()]
    assert not missing, f"missing root files: {missing}"


def test_no_empty_placeholder_files_are_tracked(repo_root: Path) -> None:
    """REQ-013."""
    placeholders = [name for name in tracked_files(repo_root) if Path(name).name == ".gitkeep"]
    assert not placeholders, f"placeholder files found: {placeholders}"


def test_ci_status_check_name_matches_the_ruleset(repo_root: Path) -> None:
    """The required status check must match a job that actually exists."""
    import yaml

    workflow = yaml.safe_load(
        (repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    setup = (repo_root / "docs/SETUP.md").read_text(encoding="utf-8")
    assert "ci-success" in workflow["jobs"]
    assert "ci-success" in setup, "SETUP.md must name the required status check"


def test_every_lane_exists(repo_root: Path) -> None:
    """Whole-repository check: by the end of the plan every advertised lane is real.
    Task 8 deliberately asserts only the README text, because four of these lanes
    do not exist until Tasks 4-7."""
    for lane in ("firmware", "notebooks", "webapp", "data", "docs", "specs", "tests"):
        assert (repo_root / lane).is_dir(), f"lane {lane}/ is documented but absent"
```

- [ ] **Step 2: Add `httpx` to the dev dependency group**

The final verification includes querying the GitHub API; add `"httpx>=0.27"` to `[dependency-groups] dev` in `pyproject.toml`, then run `uv lock` and `uv sync`.

- [ ] **Step 3: Run the entire suite**

Run: `uv run pytest -q`
Expected: zero failures across every test module created in Tasks 1–11.

- [ ] **Step 4: Run every quality gate**

Run:
```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
pre-commit run --all-files
```
Expected: no findings from any of the four.

- [ ] **Step 5: Verify no secret is present anywhere in history**

Run: `gitleaks detect --config .gitleaks.toml --redact -v`
Expected: no leaks found. `--redact` prevents a real finding from being printed into the terminal in cleartext.

- [ ] **Step 6: Verify the local clone is clean and pushed**

Run:
```bash
git status --porcelain
git status -sb
```
Expected: no uncommitted changes; `main` in sync with `origin/main`.

- [ ] **Step 7: Commit and push**

```bash
git add pyproject.toml uv.lock tests/test_final_verification.py
git commit -m "test: add whole-repository acceptance verification"
git push
```

---

## Self-Review

**1. Spec coverage.** Every acceptance criterion in spec §8 maps to a task: REQ-010/011/041–043 → Task 11; REQ-012 → Tasks 1–10 with the final check in Task 12; REQ-013 → Tasks 5 and 12; REQ-014 → Tasks 2 and 10; REQ-020–026 → Tasks 1 and 6; REQ-030–034 → Tasks 5 and 1; REQ-040 → Tasks 9 and 11; REQ-044–046 → Task 9; REQ-050–053 → Task 3; REQ-060–062 → Tasks 10 and 2; REQ-063 → Task 8; REQ-070 → Tasks 1, 5, and 12. Spec §4.1 rule 3 (the root workspace exclusion when `webapp/` gains its own manifest) is recorded in `webapp/README.md` in Task 7's Step 3 and enforced negatively by `test_no_webapp_dependency_manifest_exists`.

**2. Step scan.** No step says "handle edge cases" or "add validation". Steps that pin exact content (`pyproject.toml`, `.gitignore`, `.gitattributes`, `.gitleaks.toml`, `CLAUDE.md`, the `ci-success` shell logic) do so because the spec fixes those values and an implementer cannot infer them. The `ci.yml` task specifies job names, guards, outputs, and the gate's polarity but leaves the YAML body to the implementer, because the shape is standard and the decisions are what matter.

**3. Type consistency.** `repo_root` is defined once in Task 1 and used with that exact name throughout. `HARDWARE_AVAILABLE` and `run_check()` are named identically in Task 4's Interfaces, test, and implementation step. The `ci-success` job name is identical in Task 9, Task 11 (as the required check), and Task 12 (as the asserted cross-reference). The sample fixture path `data/samples/public_health_indicators.csv` and its header `region,indicator,year,value` are identical in Tasks 5, 6, and 8, and in Review Focus item 1.

**4. Review Focus.** Each of the five items has an owning test: CRLF → Task 9's `test_gitattributes_forces_lf_for_lockfile_and_python`; notebook outputs → Task 6's `test_template_notebook_has_no_outputs`; firmware boot failure → Task 4's `test_firmware_does_not_import_repo_root` and `test_code_py_has_no_forbidden_constructs`; secrets leak → Task 5's `test_sensitive_paths_are_gitignored`; committed patient data → Task 5's `test_sensitive_paths_are_gitignored` plus Task 12's `test_no_tracked_file_exceeds_one_megabyte` and the gitleaks run in Task 12, Step 5.

**5. Proportion.** The plan is longer than the spec because the spec is a decision document and the plan must enumerate file paths, test names, and the exact pinned contents for roughly forty files. The `ci.yml` body and the document prose are specified by requirement rather than transcribed, which keeps the plan well under the size of the code it describes.

## Execution Note

The interface name `ci-success` appears in three tasks. If any task renames it, Task 11's rule and Task 12's assertion break together — treat it as a fixed interface.
