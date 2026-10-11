# gengineer-pjdsc-2026

A public health analytics entry for the **Philippine Junior Data Science Challenge
(PJDSC) 2026**, integrating a microcontroller sensor node with a web application so
that a community-level health signal can be measured, transmitted, and read by a
non-technical health worker.

**License:** [Apache License 2.0](LICENSE)

> **Status: bootstrap.** The repository structure, toolchain, data policy, and
> governance are in place. No problem statement, dataset, or firmware feature has been
> implemented yet; see [`CHANGELOG.md`](CHANGELOG.md) for what actually exists today.
> Nothing in this repository claims results it does not have.

## The competition

| | |
|---|---|
| **Event** | Philippine Junior Data Science Challenge (PJDSC) 2026 |
| **Organizer** | UP Data Science Society (UP DSSoc), University of the Philippines |
| **Theme** | Public Health Analytics |
| **Theme title** | "Trace the Pattern, Target the Cure: Advancing Public Health Through Data Science" |
| **Judged on** | Project Rationale and Design; Execution and Impact; Code Repository (structure and documentation, reproducibility, dependencies and data management); Demonstration Video; Technical Rigor and Innovation; **Sources (reliable, up-to-date, APA 7th Edition)** |
| **Final project due** | October 24, 2026 |
| **Repository** | <https://github.com/andrewhmir/gengineer-pjdsc-2026> (public) |

The event's challenge statement asks how data analytics and innovative approaches can be
leveraged to develop practical solutions that improve disease prevention, support early
intervention, strengthen healthcare systems, and promote healthier communities. The
primer permits a solution in the form of a web application, mobile app, dashboard, or any
usable product; this team's intended direction is **microcontroller plus web
application**. The official topic list the project must be framed against is recorded in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#official-competition-topics).

This repository is a scored deliverable, so it is written to be read by a judge: every
command below runs from a clean clone, and every data source used is cited in
[`docs/SOURCES.md`](docs/SOURCES.md).

## Repository map

One line per lane. Deeper explanation, including the three-lane model and lane
boundaries, is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

| Path | Lane | State | What lives there |
|---|---|---|---|
| [`firmware/`](firmware/) | Firmware | skeleton | CircuitPython for the sensor node; copied wholesale to the board's `CIRCUITPY` USB drive. Host tests only — not yet flashed. |
| [`data/`](data/) | Data | structure | Data policy and committed sample fixtures. `raw/` and `interim/` hold local-only data that is never committed. No analysis yet. |
| [`notebooks/`](notebooks/) | Data / analysis | template | Analysis notebooks, with outputs stripped on commit. A template is committed; no analysis yet. |
| `webapp/` | Web | undecided | The user-facing application. Framework not yet chosen; [`webapp/README.md`](webapp/README.md) records the deferred decision. |
| [`submission/`](submission/) | Cross-cutting | present | The scored deliverables: the slide deck PDF, the linked demo video, and the pre-submission checklist with its hard limits. |
| [`tests/`](tests/) | Cross-cutting | present | The pytest suite that gates every lane. |
| [`docs/`](docs/) | Cross-cutting | present | Human-facing documentation: architecture, data policy, citations, owner setup. |
| `specs/` | Cross-cutting | present | Frozen design records: the approved specification and implementation plan. |

The **State** column says how far a lane has got, not how much it matters:

- **skeleton**, **structure**, **template** — the lane's scaffolding, policy, and rules are
  committed; the feature the lane exists for is not implemented yet.
- **present** — in place for the bootstrap, with nothing further sequenced.
- **undecided** — a deliberate placeholder: the directory exists, and the decision it waits
  on has not been made. `webapp/` is the only one, and its lane readme records why.
- **planned** — the directory does not exist yet, and its own lane task creates it.
  `submission/` is the only one left.

Nothing in this repository pretends an unfinished lane is finished: each lane lands as its
own reviewed change, and until then the repository contains the structure, the policy, and
the gates rather than the features. The lanes are sequenced in
[`specs/2026-10-10-repo-bootstrap-plan.md`](specs/2026-10-10-repo-bootstrap-plan.md). A
**planned** lane is shown as a plain path rather than a link, because linking to a
directory that does not exist yet would be a dead link in a judged submission; its lane
task turns it into a link as it creates the directory.

## Quickstart

Requirements: [`uv`](https://docs.astral.sh/uv/) (which installs and manages Python
itself) and Git. No other prerequisites — `uv` reads `.python-version` and resolves
Python 3.12.

```console
git clone https://github.com/andrewhmir/gengineer-pjdsc-2026.git
cd gengineer-pjdsc-2026
uv sync
uv run pytest
```

`uv sync` creates `.venv/` and installs the pinned development dependencies from
`uv.lock`. `uv run pytest` runs the whole test suite; it must pass from a clean clone
with no manual setup, no hardware attached, and no network access.

These are the only commands this repository provides:

| Command | Purpose |
|---|---|
| `uv sync` | Create/update the environment from `uv.lock`. |
| `uv run pytest` | Run the full test suite. |
| `uv run pytest -v` | Run the suite with one line per test. |
| `uv run ruff check .` | Lint. |
| `uv run ruff format --check .` | Verify formatting without writing. |
| `uv run mypy` | Type-check `tests/`. |

The local gate before a push is these four, and they mirror what CI runs:

```console
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

There is deliberately no `Makefile` and no `src/` package: the analysis code lives in
notebooks and the web code in `webapp/`, so a package abstraction would be a decision
made before it is needed. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Data policy

Short version: **structure is committed, contents are not.**

- Nothing under `data/raw/` or `data/interim/` is ever committed.
- `data/samples/` holds small, illustrative fixtures so that tests and judges can run
  the project without the full dataset. They are synthetic and labelled as such.
- **No real patient or personally identifiable health data may ever be committed.**
  Public health data in the Philippines falls under the Data Privacy Act of 2012
  (Republic Act No. 10173).
- Every dataset must be cited in [`docs/SOURCES.md`](docs/SOURCES.md) *before* it is used
  in analysis.

The full policy, including the retrieval procedure for the real datasets, is in
[`docs/DATA.md`](docs/DATA.md).

## Citations and sources

All sources are cited in **APA 7th Edition** in [`docs/SOURCES.md`](docs/SOURCES.md),
which is the single source of truth for data provenance. "Sources — reliable, up-to-date,
APA 7th Edition" is a separately scored criterion, so a dataset that is not listed there
must not appear in a notebook, a figure, or the slide deck. If you cite this repository
itself, use [`CITATION.cff`](CITATION.cff).

## Contributing

Branch naming, Conventional Commits with a lane scope, the pull request flow, and the
procedure for adding a teammate are in [`CONTRIBUTING.md`](CONTRIBUTING.md). Security and
secret handling are in [`SECURITY.md`](SECURITY.md). Owner-level operations (creating the
repository, applying the ruleset, setting labels) are in [`docs/SETUP.md`](docs/SETUP.md).

## Team

Maintained by **Andrew** ([@andrewhmir](https://github.com/andrewhmir)) and teammates as
they join. Contributors are listed in [`CITATION.cff`](CITATION.cff); the event publishes
qualifying projects with citation to each contributing member, so every teammate is added
there. Contact the maintainer by opening an issue on this repository.

## License

Licensed under the **Apache License 2.0** — see [`LICENSE`](LICENSE). Apache-2.0 was
chosen over MIT because the project includes a web application that may be deployed
publicly, and the license's explicit patent grant is the safer default for a deployed
product.
