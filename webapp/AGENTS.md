# AGENTS.md — webapp lane

Scope: everything under `webapp/`. The closest `AGENTS.md` wins, so this file overrides
the root [`AGENTS.md`](../AGENTS.md) for these paths; the root file's repository-wide
rules still apply.

## No framework has been chosen

**No framework has been chosen, and no framework decision has been made.** This lane is a
deliberate placeholder, not started work. The decision record, the candidate directions,
and the criteria for choosing all live in [`README.md`](README.md) — read that before
proposing any web work, and do not restate it here.

## Hard rules

- **Do not scaffold a framework.** No project generator of any kind — no `npm create`, no
  `django-admin startproject`, no `uv init`, no starter template. A scaffold is a
  framework decision made by an agent, which is exactly what must not happen.
- **Do not add dependencies**, and do not add a dependency manifest: no `package.json`,
  no `pyproject.toml`, no `requirements.txt`, no lockfile under `webapp/`. A placeholder
  manifest asserts a decision that has not been made. `tests/test_placeholders.py` enforces
  this by asserting the lane's directory contents exactly, so any new file here fails CI.
- **Do not restructure the repository to accommodate a web app.** No new top-level
  directory, no moving existing lanes, no `src/` extraction, no edit to the root
  `pyproject.toml` to make room for a web app.
- **Do not pick a framework "just to have something running"**, and never present a
  starter template as though the project had chosen it.
- **Do not commit a build artifact, a `node_modules/` tree, or an environment file.**
  `.env` is prohibited repository-wide; use `.env.example` for placeholder keys.

## What this lane may contain today

Only this file and the lane `README.md`, which states the deferred decision. No code, no
configuration, no assets, no manifests.

## Until a framework is chosen

Treat any proposal to "start the frontend" as **blocked on a human decision**, and say so
rather than proceeding. What that decision will require — the lane manifest and the root
`tool.uv.workspace` exclusion — is recorded in [`README.md`](README.md); do not restate it.
