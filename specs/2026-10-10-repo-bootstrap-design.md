# Repository Bootstrap Design — gengineer-pjdsc-2026

**Date:** 2026-10-10
**Status:** Draft — awaiting human review
**Author:** Andrew (with DSH agent assistant)
**Scope:** Setting up the team repository *before* the project idea is finalized.

---

## 1. Context and Goal

### 1.1 What is being built

A new public GitHub repository, `gengineer-pjdsc-2026`, owned by the personal account
`andrewhmir`, to be used by a team competing in the **Philippine Junior Data Science
Challenge (PJDSC) 2026**, organized by UP Data Science Society.

### 1.2 Why now

The competition launched on **2026-10-10**. The compressed timeline drives the decision
to scaffold first and fill in the domain logic later:

| Milestone | Date |
|---|---|
| Event launch | 2026-10-10 |
| Concept proposal deadline | 2026-10-12 |
| Project development workshop | 2026-10-17 |
| **Final project submission** | **2026-10-24** |
| Finalists announced | 2026-11-04 |
| Advanced workshop + mentorship | 2026-11-07 |
| Culminating event (live demo) | 2026-11-14 |

### 1.3 The core constraint

The competition problem is **not yet chosen**. The theme is fixed — *Public Health
Analytics*, under the title "Trace the Pattern, Target the Cure: Advancing Public Health
Through Data Science" — but the specific problem, dataset, and method are open.

Therefore the repository must be **problem-agnostic**: readiness comes from *process and
structure*, not from prematurely guessing the domain solution. Scaffolding for a specific
task (for example an image-classification pipeline) would be actively harmful if the
challenge turns out to be tabular, NLP, or time-series.

### 1.4 Known project direction

The team intends to integrate **microcontrollers** with a **web application**. The primer
explicitly permits this: solutions "may be in the form of a web application, mobile app,
dashboard, or **any usable product**." Public health framing remains required.

### 1.5 Team

Currently one person (`@andrewhmir`). The competition requires **3–5 members** by
registration, so the repository is designed for teammates to be added with minimal
ceremony (see §7.3).

---

## 2. Requirements Derived From the Official Rubric

The rubric is not inferred — it comes from the event's own published primer, read from the
source repository of the official website
(`artemiui/pjdsc26-website`, file `event-mechanics-references/[PJDSC '26] Event Primer Content.md`).
This matters because several design decisions below are *rubric-driven* rather than
general good practice.

### 2.1 The repository is directly scored

Final projects are judged on **six** criteria in the Project-Based Elimination Round. The third is
the code repository:

> **Code Repository** — *Code Structure and Documentation; Functional Execution and
> Reproducibility; Dependencies and Data Management*

The full six are: Project Rationale and Design; Execution and Impact; Code Repository;
Demonstration Video; Technical Rigor and Innovation; Sources. Note that the **Final Round** for
the top ten finalists uses a *different* set of five criteria (Demonstrated Functionality and
Technical Robustness; Impact and Real-World Applicability; User Experience and Design;
Presentation and Communication; Sources) — do not conflate the two lists.

The repository is also a mandatory deliverable: every final proposal must include "an
updated slide deck (PDF), a recorded project demonstration video, and **a link to the
complete code repository**."

### 2.2 Traceability matrix

Every rubric sub-criterion is mapped to a concrete artifact in this design.

| Rubric criterion | Sub-criterion | Design response | Artifact / requirement |
|---|---|---|---|
| Code Repository | Code Structure and Documentation | Lane-separated tree; per-lane READMEs; docs set; agent instruction files | `README.md`, `docs/ARCHITECTURE.md`, `firmware/README.md`, `REQ-010`–`REQ-014` |
| Code Repository | Functional Execution and Reproducibility | Single-command setup; locked dependencies; committed sample data; CI green from day one | `REQ-020`–`REQ-026`, `REQ-040`–`REQ-043` |
| Code Repository | Dependencies and Data Management | `uv` lockfile; explicit data policy; provenance + download script | `REQ-020`, `REQ-030`–`REQ-034` |
| Sources | Reliable, up-to-date, APA 7th Edition | Dedicated citation and provenance file | `docs/SOURCES.md`, `REQ-014` |
| Project Rationale and Design | Problem statement, data sources, methodology | `specs/` design documents; `docs/DATA.md` | `REQ-050`–`REQ-053` |
| Technical Rigor and Innovation | Validity, novelty, analytical depth | Reproducibility via locked environment and tests | `REQ-020`, `REQ-024` |
| Demonstrated Functionality (final round) | Code Quality and Reproducibility | CI enforcement, review flow, rulesets | `REQ-041`–`REQ-046` |

### 2.3 Additional rubric-driven obligations

| Obligation | Source | Design response |
|---|---|---|
| Winning projects are published on **UP DSSoc's official GitHub** with citation to each contributing member | Primer, Event Culmination §2.5 | Repository must be public-ready: no secrets, no personal health data, permissive license, `CITATION.cff` |
| Public health analytics theme | Primer, Page 2 | README and docs frame the project under this theme; topics list referenced in `docs/ARCHITECTURE.md` |
| Slide deck ≤ 20 slides; demo video ≤ 3 minutes; point deductions for overage | Primer, Project Development §3 | Dedicated `submission/` lane with explicit limits recorded in `submission/README.md` |
| Data privacy for health data (Data Privacy Act of 2012, RA 10173) | Inferred risk, not stated in primer | Explicit "no real patient data" rule in `docs/DATA.md` and `SECURITY.md` |

### 2.4 What the rubric does *not* justify

To keep scope honest, the following are explicitly **not** required by the rubric and are
therefore excluded: DVC or Git LFS, containerization, a docs website, a model registry, a
`src/` package, and a `Makefile`. Each is deferred in §9 with a stated trigger for
revisiting.

---

## 3. Chosen Approach

Three approaches were considered:

- **A. Conventional `src/`-layout Python package with docs-as-code** — the least surprising
  repository shape, but it commits to a package abstraction before knowing whether shared
  code is needed.
- **B. Notebook-first, minimal scaffolding (chosen)** — notebooks carry the data/analysis
  code; no package; structure provides the readiness.
- **C. Full template (Makefile, DVC, pre-commit, docs site, container)** — rejected as YAGNI;
  it commits to data-versioning and compute assumptions before the data shape is known.

**Approach B was selected, revised for a systems project.** Because the intended direction
integrates microcontrollers and a web application, the repository is not a pure
data-science repository: it hosts three sibling *lanes* under one history, because
integration changes touch more than one lane and should be reviewable in a single pull
request.

### 3.1 Decision: CircuitPython for firmware

Firmware is written in **CircuitPython**, not Arduino/C++. This keeps one language across
data, firmware, and (if Python) web app, so a single CI pipeline can gate all lanes.

Accepted cost: CircuitPython is not full Python — no `dataclasses`, no `match`, no
`X | Y` type syntax, and only the standard library plus the Adafruit bundle. `py_compile`
accepts code that will still crash on boot, so this constraint is recorded as an explicit
rule in `firmware/AGENTS.md` and `firmware/README.md`.

### 3.2 Decision: public repository

The repository is **public from the start**. Rationale:

1. The rubric scores reproducibility, and a judge must be able to open the submission link.
2. The event publishes qualifying projects publicly and frames open sharing as a core value.
3. On a **public** repository, GitHub Free includes **rulesets and branch protection** —
   governance becomes *enforced* rather than merely documented. This is a strict improvement
   over the private-repository case, where such rules require a paid plan.

Accepted risk: other teams can see the work from day one.

---

## 4. Repository Layout

```
gengineer-pjdsc-2026/
├── .github/
│   ├── workflows/ci.yml
│   ├── ISSUE_TEMPLATE/{config.yml,bug_report.md,feature_request.md,task.md}
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── CODEOWNERS
│   └── dependabot.yml
├── firmware/                  # CircuitPython; copied to the CIRCUITPY drive
│   ├── AGENTS.md
│   ├── README.md
│   ├── code.py                # entry point (auto-runs on boot)
│   ├── lib/                   # vendored drivers; README.md only at bootstrap
│   ├── secrets.example.py
│   ├── config.example.toml
│   └── .gitignore
├── data/                      # contents gitignored; structure committed
│   ├── README.md
│   ├── raw/README.md
│   ├── interim/README.md
│   └── samples/               # small fixtures that ARE committed
├── notebooks/
│   ├── AGENTS.md
│   ├── README.md
│   └── _template.ipynb
├── webapp/
│   ├── AGENTS.md
│   └── README.md
├── submission/                # NEW (rubric-driven)
│   └── README.md              # deck index, video link, hard limits, checklist
├── tests/
│   ├── AGENTS.md
│   ├── conftest.py
│   └── test_repo_smoke.py
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── DATA.md
│   ├── SOURCES.md             # NEW (rubric-driven): APA 7th citations + provenance
│   └── SETUP.md
├── specs/
│   ├── README.md
│   └── 2026-10-10-repo-bootstrap-design.md
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── CITATION.cff               # public-ready, per event publication
├── LICENSE
├── .editorconfig
├── .gitignore
├── .pre-commit-config.yaml
├── .gitleaks.toml
├── .python-version
├── pyproject.toml
└── uv.lock
```

### 4.1 Design rules encoded in the layout

1. **`firmware/` is not a Python package.** The board mounts as a `CIRCUITPY` USB drive, so
   the folder is copied wholesale onto it. It must therefore be flat, dependency-free, and
   must not import from the repository root. Code intended for sharing goes *into*
   `firmware/lib/`.
2. **No `src/` package.** Notebooks carry the analysis code; `webapp/` carries web-facing
   code. If a third consumer of shared logic appears, a `src/` package is extracted *then* —
   an additive change, not a rewrite.
3. **One `pyproject.toml`, at the root only.** `webapp/` receives its own only when it has
   real code, at which point the root `pyproject.toml` gains an explicit `tool.uv.workspace`
   exclusion so `uv sync` at the root does not attempt to resolve it. A placeholder
   `pyproject.toml` would be a lie about a decision not yet made.
4. **`data/` structure is committed; `data/raw/` and `data/interim/` contents are not.**
   Each subfolder carries a `README.md` rather than a bare `.gitkeep`, because the README
   carries real guidance — this avoids the "placeholder file" anti-pattern.
5. **`submission/` is a first-class lane** because deck, video, and checklist are scored
   deliverables with hard numeric limits.

---

## 5. Agent Instruction Layer

`AGENTS.md` is the emerging cross-tool standard for coding-agent instructions. The
standard supports **nested files with nearest-file precedence**: the closest `AGENTS.md` to
the file being edited takes effect, and the root file provides the fallback. Explicit user
instructions in chat override everything.

Reference: <https://mintlify.wiki/agentsmd/agents.md/guides/monorepos>

Claude Code reads `AGENTS.md` natively from v2.1.277 onward, but **only when no `CLAUDE.md`
exists in or above the working directory**. A sibling `CLAUDE.md` containing the single line
`@AGENTS.md` makes the content load even in sessions that cannot read `AGENTS.md` directly.

Reference: <https://code.claude.com/docs/en/memory>

Because the lanes have genuinely different rules, one root file would be a blob that loads
on every task. The nested structure is therefore used:

| File | Scope | Rationale |
|---|---|---|
| `AGENTS.md` | whole repository | Structure, commands, branch/PR conventions, data policy, hard prohibitions, known environment constraints |
| `firmware/AGENTS.md` | firmware lane | **Protects vendored `lib/` from edits**; documents the CIRCUITPY copy-deploy model; forbids importing from the repository root; records the CircuitPython language subset; explains host-side testing with fakes |
| `notebooks/AGENTS.md` | notebooks | Clear outputs before commit; no absolute paths; real logic belongs in importable modules, not cells; deterministic seeds |
| `tests/AGENTS.md` | tests | No hardware and no network in tests; use `data/samples/` fixtures; mock the board |
| `webapp/AGENTS.md` | webapp | Placeholder stating that no framework decision has been made, so an agent does not invent one |
| `CLAUDE.md` | compatibility shim | Single `@AGENTS.md` import, plus Claude-specific content below it |

`GEMINI.md` is **not** created: Gemini CLI reads `AGENTS.md` natively.

**Content discipline.** These files are operational, not narrative. Each targets well under
200 lines, because longer instruction files measurably reduce adherence. They state
commands, hard rules, and gotchas, and they deliberately do **not** duplicate `README.md` or
`CONTRIBUTING.md` — where they overlap, they point at the human-facing document.

---

## 6. Tooling and CI

### 6.1 Root toolchain

| Concern | Choice | Rationale |
|---|---|---|
| Interpreter | Python 3.12, pinned in `.python-version` and `requires-python` | Safe, widely available floor. CircuitPython compatibility is governed separately and is not a function of this version. |
| Environment / packages | `uv` with `pyproject.toml` + `uv.lock` | One command (`uv sync`) for teammates; lockfile serves the "Dependencies" rubric criterion; identical in CI |
| Lint and format | `ruff` (both lint and formatter), line length 100 | One tool instead of black + isort + flake8; rule sets `E,F,W,I,UP,B,SIM` |
| Types | `mypy`, non-strict initially | Strict mode on an empty repository is friction; tighten as real code lands |
| Tests | `pytest` + `pytest-cov`, `nbmake` for notebooks | `nbmake` executes notebooks in CI |
| Pre-commit | `.pre-commit-config.yaml` | Whitespace/EOF, YAML/TOML/JSON validity, ruff, `nbstripout`. Deliberately **no** gitleaks hook: the upstream hook uses `language: golang` and would make `pre-commit run --all-files` unrunnable without a Go toolchain. |

### 6.2 Firmware testing — honest scope

| Capability | Possible? | Mechanism |
|---|---|---|
| Verify firmware byte-compiles | **Yes** | `python -m py_compile` over all `firmware/**/*.py` in CI |
| Verify firmware *runs* on the device | **No** | Requires a human flashing real hardware. This limitation is stated in `firmware/README.md` rather than implied away. |
| Unit-test firmware logic on the host | **Yes** | Firmware imports hardware modules behind a seam so tests can inject fakes for `board`, `busio`, `digitalio` |

### 6.3 CI workflow

`.github/workflows/ci.yml`. Design goal: **green on day one, and still correct once lanes
are implemented.** Every job except the aggregate gate carries a changed-path guard, so an
unimplemented lane never fails a pull request.

| Job | Runs when | Purpose |
|---|---|---|
| `changes` | always | Computes changed paths; other jobs gate on it |
| `lint` | root Python changed | `ruff check`, `ruff format --check`, `mypy` |
| `test` | root or `tests/` changed | `pytest -q` |
| `notebooks` | `notebooks/` changed | `nbmake` executes every `notebooks/*.ipynb`. **There is no tag-based opt-in:** nbmake's collection predicate is `nbmake_enabled and p.match("*ipynb") and "_build" not in p.parts`, so being in `notebooks/` is the opt-in. The `nbmake` marker tag `nbmake` has no effect and is not used. |
| `firmware` | `firmware/` changed | `py_compile` all firmware Python |
| `secrets` | always | Enforcement point for secret scanning: installs and runs the gitleaks CLI (`gitleaks detect --config .gitleaks.toml --redact -v`) over full history. Not a backstop — there is deliberately no pre-commit hook, because that hook needs a Go toolchain. The free CLI is used rather than `gitleaks/gitleaks-action@v2`, which is license-gated. |
| `ci-success` | always | Aggregate gate reporting **success** when upstream jobs were skipped |

The `ci-success` job is load-bearing, not decorative: a required status check whose job is
skipped never reports, which would leave pull requests permanently unmergeable once
enforcement is enabled.

### 6.4 Bootstrap detail

`pytest` exits with **code 5 (failure)** when it collects zero tests, so an empty `tests/`
would break CI on day one. `tests/test_repo_smoke.py` therefore asserts real invariants
(directories exist, Python is pinned, `.gitleaks.toml` present). These are genuine
assertions, not placeholders — the test fails if a lane is deleted or the pin removed.

`.gitignore` will contain **no trailing comments**: a pattern line such as
`data/raw/   # datasets` becomes a literal never-matching pattern. Comments go on their own
lines.

---

## 7. Collaboration Conventions

### 7.1 Branching

`main` is the default branch. Nothing lands on it directly, including by the repository
owner. Lanes match directories:

- `firmware/*`, `data/*`, `notebooks/*`, `webapp/*` — lane work
- `docs/*`, `chore/*` — cross-cutting work
- `specs/*` — design documents

Lowercase, hyphenated. Integration work that spans lanes is allowed and encouraged, but the
pull request must name every lane it touches.

### 7.2 Commits

[Conventional Commits](https://www.conventionalcommits.org/) with a lane scope, for example
`feat(firmware): add DHT22 temperature reader`. One logical change per commit.

**House rule:** no AI attribution trailers — no `Co-Authored-By`, no "Generated with"
footer. Commits read as the human author's work. This is a deliberate choice for a judged
competition submission and is overridable by the maintainer.

### 7.3 Review

- At least **one approval** before merge.
- `CODEOWNERS` lists `@andrewhmir` for all paths at bootstrap.
- **Add-a-teammate procedure** is documented in `CONTRIBUTING.md`: invite as collaborator,
  add the handle to `CODEOWNERS`, add to `CITATION.cff` contributors.
- Because the team is currently one person, a two-approval rule would deadlock. Until a
  second contributor exists, pull requests are self-reviewed; the pull request description
  still serves as the record of *why*.

### 7.4 Enforcement

On a public repository, GitHub Free permits rulesets. The following are configured and
**verified** during implementation:

1. Block force-push and deletion on `main`. — safe unconditionally
2. Require a pull request before merging. — safe unconditionally
3. Require the `ci-success` status check to pass. — safe unconditionally
4. Require linear history; require conversation resolution. — safe unconditionally

**Required approvals are handled differently, and this is deliberate.** GitHub does not
permit a pull request author to approve their own pull request. While the team has exactly
one contributor, enabling "require 1 approval" would make `main` **unmergeable** — every PR
would be permanently blocked with no eligible approver. Therefore:

- The ruleset is created **without** a required-approval count at bootstrap.
- The approval requirement is enabled as part of the add-a-teammate procedure in
  `CONTRIBUTING.md`, which is the first moment an eligible approver exists.
- The exact `gh api` command to enable it is recorded in `docs/SETUP.md`, so it is a
  one-line change rather than a rediscovery.

If any rule is rejected by the GitHub API, implementation falls back to documenting the
rule in `docs/SETUP.md` with the exact `gh api` command to apply it later, and the
outcome is reported honestly rather than assumed.

### 7.5 Issues

Templates: `bug_report`, `feature_request`, `task` (lane-agnostic).
Labels: `lane:firmware`, `lane:data`, `lane:notebooks`, `lane:webapp`, `lane:docs`,
`submission`, plus `priority:*` and `type:*`.

### 7.6 Secrets and privacy

- `firmware/secrets.py` is gitignored; `firmware/secrets.example.py` is committed. WiFi
  credentials pasted into firmware are the single most common CircuitPython leak.
- `.env` gitignored; `.env.example` committed.
- gitleaks runs in CI only, as the `secrets` job. There is no pre-commit gitleaks hook, because
  the upstream hook requires a Go toolchain and would break `pre-commit run --all-files` for any
  contributor without Go.
- **No real patient or personally identifiable health data may be committed.** Public health
  data in the Philippines falls under the Data Privacy Act of 2012 (RA 10173). This is
  recorded in `docs/DATA.md` and `SECURITY.md`.
- `SECURITY.md` documents how to report a leak and how to rotate a compromised credential.

### 7.7 Data

- Nothing under `data/raw/` or `data/interim/` is committed.
- `data/samples/` holds small committed fixtures so tests and notebooks run without the full
  dataset. Bootstrap commit includes a small public-health-shaped sample in CSV
(`data/samples/public_health_indicators.csv`, header `region,indicator,year,value`) plus its
  provenance.
- The full dataset is retrieved by a documented script; its source, license, and APA 7th
  citation live in `docs/SOURCES.md`.
- This combination is chosen specifically because the rubric scores both *reproducibility*
  (a judge can run something immediately) and *data management* (the repository is not a
  dumping ground for large files).

### 7.8 Notebooks

Outputs are stripped by `nbstripout` on commit. No absolute paths. Logic needed by more than
one notebook does not live in a cell.

### 7.9 Language

All repository content is written in English. This is an assumption recorded for correction,
not a constraint imposed by the rubric.

---

## 8. Acceptance Criteria

The bootstrap is complete when all of the following are demonstrably true.

| ID | Criterion | Verification |
|---|---|---|
| REQ-010 | Repository exists at `github.com/andrewhmir/gengineer-pjdsc-2026`, public | `gh repo view` |
| REQ-011 | Default branch is `main`, with an initial commit on it | `git log --oneline main` |
| REQ-012 | All files in §4 exist except those explicitly deferred in §9 | `Get-ChildItem -Recurse` comparison |
| REQ-013 | No `.gitkeep` or other empty placeholder files are committed | manual review |
| REQ-014 | `docs/SOURCES.md` exists and contains at least one APA 7th-formatted source | read file |
| REQ-020 | `uv sync` succeeds from a clean clone | run in a fresh clone |
| REQ-021 | `uv.lock` is committed | `git ls-files uv.lock` |
| REQ-022 | `requires-python` and `.python-version` agree | read both |
| REQ-023 | `ruff check` and `ruff format --check` pass with zero findings | run locally |
| REQ-024 | `uv run pytest` passes and collects at least one real test | run locally |
| REQ-025 | `pre-commit run --all-files` passes | run locally |
| REQ-026 | `nbstripout` strips outputs; a test notebook proves it | commit a notebook with output, verify clean |
| REQ-030 | `data/raw/` and `data/interim/` contents are gitignored; `data/samples/` is committed | `git check-ignore`, `git ls-files` |
| REQ-031 | `git ls-files` shows no file over 1 MB | `git ls-files \| measure` |
| REQ-032 | Data policy and privacy rule are documented in `docs/DATA.md` | read file |
| REQ-033 | A dataset download script or documented retrieval procedure exists | read file |
| REQ-034 | `data/samples/` contains a committed sample plus provenance | `git ls-files data/samples` |
| REQ-040 | CI is green on the bootstrap pull request | GitHub Actions run |
| REQ-041 | Ruleset blocks force-push and deletion on `main` | `gh api` read-back |
| REQ-042 | Ruleset requires a pull request before merging, and does **not** require an approval while the team has one contributor | `gh api` read-back; verify a solo PR is still mergeable |
| REQ-043 | Ruleset requires the `ci-success` check | `gh api` read-back |
| REQ-044 | `CODEOWNERS` is valid and lists the owner for all paths | GitHub parses it without error |
| REQ-045 | Issue templates and pull request template render | open the forms on GitHub |
| REQ-046 | Pull request template requires what/why/verification/lane | read file |
| REQ-050 | Root `AGENTS.md` exists and is under 200 lines | read + count |
| REQ-051 | Lane `AGENTS.md` files exist for `firmware`, `notebooks`, `tests`, `webapp` | `git ls-files */AGENTS.md` |
| REQ-052 | `CLAUDE.md` imports `AGENTS.md` via `@AGENTS.md` | read file |
| REQ-053 | `firmware/AGENTS.md` forbids editing vendored `lib/` and states the CircuitPython subset | read file |
| REQ-060 | `submission/README.md` records the 20-slide and 3-minute limits and the checklist | read file |
| REQ-061 | `CITATION.cff` is valid and lists contributors | `cffconvert` or schema review |
| REQ-062 | `LICENSE` is present and permissive | read file |
| REQ-063 | README quickstart works verbatim from a clean clone | follow it literally |
| REQ-070 | No secret, credential, or real patient data is present | `gitleaks detect` clean |

---

## 9. Deferred Decisions

Deliberately **not** decided or implemented now, each with a trigger for revisiting.

| Deferred item | Revisit when |
|---|---|
| Web application framework | The problem statement is fixed and the first web feature is scheduled |
| Microcontroller board and sensor set | Hardware is chosen; `firmware/config.example.toml` is then specialized |
| Cloud / compute target (CPU vs GPU) | A model or dataset exceeds local capacity |
| DVC or Git LFS | Committed sample or model artifacts approach repository size limits |
| Containerization | Deployment target requires it |
| `src/` package extraction | A third consumer of shared logic appears |
| Model registry / experiment tracking | More than one model variant is under comparison |
| Docs site (GitHub Pages) | Documentation outgrows `docs/` |
| GitHub Projects board | The issue volume exceeds what labels handle |
| AP CSP / copilot instruction file | A tool in use does not read `AGENTS.md` |

---

## 10. Implementation Notes and Known Constraints

### 10.1 GitHub identity

The repository is owned by `andrewhmir`, which is **not** the currently active `gh` account
(`andrew-aira` is active). Creating the repository and pushing requires switching:

```powershell
gh auth switch --user andrewhmir
gh auth setup-git
gh auth status   # active account must read andrewhmir
```

**Known constraint:** `gh auth switch` writes to `%APPDATA%\GitHub CLI\hosts.yml`, which is
outside the session workspace and was **blocked by the confined file sandbox** that was in
force when this spec was written.

> **Superseded 2026-10-10.** The session's file policy was subsequently raised to
> `danger-full-access`, which removes the restriction. Remote creation, push, and ruleset
> application are therefore performed by the agent as an ordinary implementation task
> (implementation plan Task 11) rather than handed to the maintainer as a runbook. The
> switch step is retained in `docs/SETUP.md` because it remains required whenever the
> active `gh` account is not `andrewhmir`.

### 10.2 Repository location

Local clone: `C:\Users\Andrew\Desktop\Gengineer\gengineer-pjdsc-2026`
(as a subfolder, keeping the workspace root clean).

### 10.3 Commit identity

Commit authorship comes from the repository-local git identity and must be set explicitly:

```powershell
git config user.name  "Andrew"
git config user.email "<andrewhmir email>"
```

No `Co-Authored-By` trailers are added, per §7.2.

### 10.4 Environment facts verified on this machine

- `git` is present at `C:\Program Files\Git\cmd\git.exe`
- `uv` is present at `C:\Users\Andrew\.local\bin\uv.exe`
- Only Windows PowerShell 5.1 is available; `pwsh` does not exist
- `git` has `core.autocrlf=true`; `.gitattributes` is therefore considered for LF enforcement
  on shell scripts, should any be added later

---

## 11. Open Items for the Maintainer

| # | Item | Impact |
|---|---|---|
| 1 | Team name for the README and `CITATION.cff` | Cosmetic; can be added before the Oct 24 submission |
| 2 | Teammate GitHub handles | Needed for `CODEOWNERS`, `CITATION.cff`, collaborator invites |
| 3 | License confirmation (Apache-2.0 proposed) | Patent grant is desirable if the web app is deployed; MIT is the simpler alternative |
| 4 | Whether the demo video is committed or linked | Committing keeps the repository self-contained for judges; linking avoids a large binary. `submission/README.md` initially documents a link, with the deck PDF committed. |
| 5 | Confirm English-only documentation | Currently assumed |
