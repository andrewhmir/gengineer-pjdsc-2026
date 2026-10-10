# Documentation

Human-facing documentation for `gengineer-pjdsc-2026`. This index is the entry point for
anyone who has already read the root [`README.md`](../README.md) and wants the detail
behind it.

If you are an automated agent looking for operational rules and commands, read the
`AGENTS.md` file closest to the file you are editing instead — starting at
`../AGENTS.md`. The `AGENTS.md` files deliberately do not duplicate these
documents; they point at them.

## This directory

| Document | Read it when you need |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The three-lane model, why the repository has no `src/` package, the `CIRCUITPY` deploy constraint, the vendoring rule for `firmware/lib/`, and the official competition topic list. |
| [`DATA.md`](DATA.md) | The data policy: what may and may not be committed, where full datasets come from, how to retrieve them, and the Data Privacy Act (RA 10173) prohibition on real patient data. |
| [`SOURCES.md`](SOURCES.md) | Data provenance and citations in APA 7th Edition. **The single source of truth for every dataset and source used in this project.** |
| [`SETUP.md`](SETUP.md) | Owner-level operations in exact commands: creating the repository, the `gh auth switch` requirement, applying the ruleset, enabling required approvals, setting labels. |

## Elsewhere in the repository

| Document | Read it when you need |
|---|---|
| [`../README.md`](../README.md) | The project overview, competition context, repository map, and quickstart. Start here. |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Branch naming, Conventional Commits with a lane scope, the pull request flow, and how to add a teammate. |
| [`../SECURITY.md`](../SECURITY.md) | Secret handling, how secret scanning actually runs, how to report a leak, and how to rotate a credential. |
| [`../CHANGELOG.md`](../CHANGELOG.md) | What has landed, per version, in human-readable form. |
| [`../LICENSE`](../LICENSE) | Apache License 2.0. |
| [`../CITATION.cff`](../CITATION.cff) | How to cite this project, and the list of contributing members. |
| `../data/README.md` | The data policy in brief, next to the data it governs. |

## `specs/` — frozen design records

`specs/` holds the design documents this repository was built from, kept **as approved**.
It has no index file; these are the two documents in it:

| Document | Contents |
|---|---|
| [`../specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md) | The repository bootstrap design: requirements derived from the official rubric, the chosen approach, the layout, the toolchain, the collaboration conventions, and the acceptance criteria (`REQ-0xx`). |
| [`../specs/2026-10-10-repo-bootstrap-plan.md`](../specs/2026-10-10-repo-bootstrap-plan.md) | The implementation plan: the tasks that produce the design above, each with its test and verification step. |

These files are **historical records, not living documentation**. They are excluded from
`ruff` formatting for that reason, and they are not edited to match later reality: a
decision that changes is recorded in the design document's own superseded notice, in
[`CHANGELOG.md`](../CHANGELOG.md), and in the document that governs current behaviour.
When `specs/` and a living document disagree, the living document wins.

## Writing documentation here

- **English only**, throughout the repository.
- Every command in a document must actually run. Do not document a tool that is not
  configured, and do not add a `Makefile` to make a command look tidier.
- Do not add a CI badge for a workflow that does not exist yet.
- Link between documents rather than restating them; duplicated text goes stale silently.
- If you change a documented path or command, update every living document that mentions
  it. Historical prose in `specs/` is exempt.
