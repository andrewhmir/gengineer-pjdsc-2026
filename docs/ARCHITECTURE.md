# Architecture

Why this repository is shaped the way it is. Read this before adding a top-level
directory, moving code between lanes, or deciding where a new file belongs.

For the commands, hard rules, and known environment constraints, see the root
`AGENTS.md` (agents) and [`CONTRIBUTING.md`](../CONTRIBUTING.md) (humans).

## The problem this shape solves

The project integrates a **microcontroller sensor node** with a **web application**. That
is not a pure data-science repository: integration changes legitimately touch firmware,
the analysis notebooks, and the web app in one change, and they should be reviewable in a
single pull request. The repository therefore hosts sibling **lanes under one history**
rather than one directory tree per discipline or one repository per component.

## The three-lane model

| Lane | Directory | Language / toolchain | Deploy model | What it owns |
|---|---|---|---|---|
| Firmware | `firmware/` | CircuitPython, executed on the board | **Copied** wholesale to the board's `CIRCUITPY` USB drive | Reading sensors and posting a reading to an endpoint. |
| Data / analysis | `data/`, `notebooks/` | Python 3.12 via `uv`, Jupyter | Runs on a laptop or CI, against committed samples | Acquiring, cleaning, and analysing the public health data. |
| Web | `webapp/` | Python 3.12 via `uv` — FastAPI, Jinja2, vanilla JS on canvas | Served over HTTP by `uv run hinigram` | The screening station a patient stands in front of. |

Two further directories are **cross-cutting** and do not constitute a fourth lane:

| Directory | Role |
|---|---|
| [`tests/`](../tests/) | One pytest suite that gates every lane. No hardware, no network. |
| `submission/` | The scored deliverables themselves: slide deck, demo video link, checklist with its hard limits. |

Cross-lane integration work is expected and encouraged. A pull request that spans lanes
must **name every lane it touches** in its description.

## Design rules

These are the constraints that follow from the lane model. Each one exists because the
obvious alternative breaks something specific.

### 1. `firmware/` is copied to `CIRCUITPY`, and never imports from the repository root

The board mounts as a USB mass-storage drive named `CIRCUITPY`. Deploying means **copying
the contents of `firmware/` onto that drive** — there is no packaging step, no installer,
and no import path that reaches back into this repository. The repository does not travel
with the code.

Consequences, all of which are enforced by tests in [`tests/`](../tests/):

- `firmware/` must be **flat and dependency-free**. A module in `firmware/` may import the
  CircuitPython standard library and the Adafruit bundle. It may **never** import from the
  repository root — not `data`, not `webapp`, not `tests`. Such an import works on a
  laptop with the repository checked out and fails immediately on the board.
- A module shared between firmware files is a **first-party module sitting beside
  `firmware/code.py`**, because the lane is flat and the board resolves its own directory.
  It does **not** go into `firmware/lib/`: that directory holds vendored Adafruit-bundle
  code and is never hand-edited (§2). Putting first-party code there would hide it from
  review and from the tools that exclude `lib/`.
- `firmware/code.py` is the auto-running entry point; the board executes it on boot.
- Hardware access sits behind a seam so that host-side tests can inject fakes for `board`,
  `busio`, and `digitalio`, which do not exist off-device.
- CircuitPython is **not** CPython: no `dataclasses`, no `match`, no `X | Y` type syntax.
  `py_compile` accepts code that will still crash on boot, so lint and byte-compilation
  are necessary but not sufficient.

**What CI can and cannot prove.** CI byte-compiles every `firmware/**/*.py` (excluding
`lib/`), and checks that no firmware source imports a host-only root module and that
`code.py` avoids CircuitPython-forbidden constructs. CI **cannot** prove the code runs on
the board. A human must flash it to verify. This limitation is stated here rather than
implied away.

### 2. `firmware/lib/` is vendored third-party code — never hand-edited

`firmware/lib/` holds drivers taken from the Adafruit CircuitPython bundle at a pinned
version. They are **not ours**. Do not edit them, reformat them, or "fix" a lint finding
inside them; if a vendored file trips a tool, exclude the directory from the tool. To
update, re-copy from the Adafruit bundle at the new pinned version and record the change.
See `firmware/README.md` for the pin and the refresh procedure.

### 3. There is no `src/` package

The analysis code lives in notebooks; the web code lives in `webapp/`. A package
abstraction would commit to a shared-code boundary before anything is shared, and it would
have to be undone or worked around the first time the boundary is wrong. If a third
consumer of shared logic appears, `src/` is extracted **then** — an additive change, not a
rewrite. This is recorded as a deferred decision in
[`specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md) §9.

### 4. One `pyproject.toml` at the root, and one inside `webapp/`

The root `pyproject.toml` builds no package and resolves the analysis and test tooling. The
root project sets `package = false` under `[tool.uv]`: this repository ships no importable
package, so `uv` must not try to build or install the project itself.

`webapp/` has its own manifest and lockfile because it has a different runtime shape — a
served application with its own console script, not a notebook environment — and because a
judge must be able to run it without the analysis dependencies. The root project excludes
the lane from its workspace, so a `uv sync` at the root neither resolves nor installs it.
Two environments, one repository: the browser application is not a notebook dependency and
the notebooks are not a server dependency.

### 5. `data/` keeps its structure in Git and its contents out

`data/raw/` and `data/interim/` are gitignored. `data/samples/` holds small, synthetic
fixtures that **are** committed, so that the test suite and a judge can both run something
immediately without the full dataset. Each data subdirectory carries a `README.md` rather
than a bare `.gitkeep`, because a README can carry real guidance while an empty
placeholder cannot. Full policy: [`DATA.md`](DATA.md).

### 6. `submission/` is a first-class lane

The slide deck, the demo video, and the checklist are **scored deliverables with hard
numeric limits** (a maximum of 20 slides and a 3-minute video, with point deductions for
overage). They get their own directory and their own README rather than being scattered
into `docs/`.

## Official competition topics

The PJDSC 2026 primer lists the topics that fall under the Public Health Analytics theme.
It says the list is not exhaustive, but new work should be framed against it — if a
proposed feature does not map to a topic below, say which one it extends and why.

1. Disease Surveillance and Outbreak Monitoring
2. Disease Risk Prediction and Early Detection
3. Epidemiological Modeling and Transmission Analysis
4. Healthcare Resource Planning and Optimization
5. Healthcare Access and Service Delivery
6. Community Health Assessment and Intervention
7. Environmental Health and Risk Analysis
8. Health Behavior and Population Trends
9. Digital Health Systems and Applications
10. Public Health Communication and Decision Support

Source and full citation: [`SOURCES.md`](SOURCES.md).

The primer also fixes the shape a solution may take: "a web application, mobile app,
dashboard, or any usable product". This team's intended direction — a microcontroller
sensor node feeding a web application — falls under **Digital Health Systems and
Applications**, and must also identify at least one concrete public health problem and one
proposed method of mitigating it.

## Request and data flow (intended)

Nothing below is implemented yet. It is recorded so that lane boundaries are fixed before
code is written, and so that a later reader can tell an unimplemented design from an
implemented one.

```text
  sensor(s)                 microcontroller                    service                 user
 ┌──────────┐   electrical  ┌───────────────┐   HTTPS POST   ┌───────────┐   HTTP   ┌──────────┐
 │ DHT22 /  │──────────────▶│ firmware/     │───────────────▶│ webapp/   │─────────▶│ browser  │
 │ other    │               │ CircuitPython │  sensor token  │ API + UI  │          │ (health  │
 │ sensor   │               │ on CIRCUITPY  │                │           │          │  worker) │
 └──────────┘               └───────────────┘                └─────┬─────┘          └──────────┘
                                                                  │
                                                                  ▼
                                                            ┌───────────┐
                                                            │ data/     │
                                                            │ + notebks │
                                                            └───────────┘
```

The firmware never talks to a database and never holds a long-lived secret beyond the
sensor token. The web application owns identity, storage, and presentation. Analysis
reads from the service's exported data, not from the board.

## Deferred decisions

Deliberately not decided yet, each with the trigger that reopens it. The authoritative
table is §9 of [`specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md);
in summary: web framework, board and sensor set, compute target, DVC or Git LFS,
containerisation, `src/` extraction, model registry, docs site, and a project board.

## Related documents

- [`DATA.md`](DATA.md) — the data policy and the privacy rule.
- [`SOURCES.md`](SOURCES.md) — citations and provenance, APA 7th Edition.
- [`SETUP.md`](SETUP.md) — owner-level operations and the ruleset.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — branches, commits, pull requests.
