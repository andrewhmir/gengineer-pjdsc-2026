# AGENTS.md — webapp lane

Scope: everything under `webapp/`. The closest `AGENTS.md` wins, so this file overrides
the root [`AGENTS.md`](../AGENTS.md) for these paths; the root file's repository-wide
rules still apply.

## No framework has been chosen

**No framework has been chosen, and no framework decision has been made.** This lane is a
deliberate placeholder. It exists so that the lane is discoverable and so the absence of a
decision is explicit rather than accidental — not because web work has started.

The decision has **not been made** because it cannot be made yet: the choice follows from
the competition problem statement, which is not fixed. Once it is fixed, a human chooses
the framework, records the decision, and only then does code appear in this lane. See the
deferred-decision record in [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Hard rules

- **Do not scaffold a framework.** No project generator of any kind — no `npm create`, no
  `django-admin startproject`, no `uv init`, no starter template. A scaffold is a
  framework decision made by an agent, which is exactly what must not happen.
- **Do not add dependencies**, and do not add a dependency manifest: no `package.json`,
  no `pyproject.toml`, no `requirements.txt`, no lockfile under `webapp/`. A placeholder
  manifest asserts a decision that has not been made, and the repository's placeholder
  tests reject one.
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

## When a framework is chosen

The human who chooses it records the decision in the lane `README.md`, adds the lane's
own dependency manifest, and adds an explicit `tool.uv.workspace` exclusion to the root
`pyproject.toml` so a root `uv sync` does not try to resolve the new manifest. Until that
happens, treat any proposal to "start the frontend" as blocked on a human decision, and
say so rather than proceeding.
