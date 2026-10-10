# `webapp/` — deferred decision

This lane is the user-facing half of the entry: the thing a health worker or a judge
actually looks at, and the destination for the readings collected by the CircuitPython
sensor node in [`firmware/`](../firmware/README.md).

**No framework has been chosen, and no framework decision has been made.** The lane is a
deliberate placeholder. It exists so the lane is discoverable and so the absence of a
decision is explicit and visible, rather than something a reader has to infer from an
empty directory or an agent discovers by inventing one.

The decision has not been made because it cannot be made yet: the choice follows from the
competition problem statement, and the problem is not fixed. Committing to a framework
now would be committing to an answer before the question is known, and it would be paid
for later — in a rewrite, or in a stack that cannot be reproduced by a judge.

Until a human makes the decision, this lane contains exactly two files: this one and the
lane's operative rules in [`AGENTS.md`](AGENTS.md).

## Candidate directions

These are the directions to evaluate **once the problem is fixed**. They are options, not
candidates competing for a default, and nothing here is a shortlist that the first line
of code may assume.

- **A served dashboard.** A local server renders charts and tables from the analysis
  outputs, so a judge can re-run a live view rather than read static numbers.
- **A static report page.** Pre-rendered HTML, or a document generated from the
  notebooks, that states the findings and needs no server at all.
- **An API.** A small service exposing the processed readings over HTTP, with the
  presentation built separately against it.

A combination is possible and expected — a static page plus a served API is a common
shape for this kind of entry. The direction is chosen after the problem statement, not
before it.

## How the direction will be chosen

**Judge reproducibility comes first.** The rubric scores *Functional Execution and
Reproducibility*, and an entry a judge cannot run on a clean machine scores nothing on
that axis no matter how good it looks. The criteria, in priority order:

1. **Judge reproducibility.** Does it run from a clean clone, on a machine with only the
   documented prerequisites, with no manual setup and no network access at run time? If
   two directions are otherwise equal, this one decides.
2. **Fit to the problem.** Does it make the specific findings the problem asks for
   legible, rather than presenting generic charts that could belong to any dataset?
3. **Reproducibility of the numbers.** Does the view read from committed, reproducible
   analysis outputs, rather than from numbers typed into a template by hand?
4. **Audience.** Is it usable by the people the problem names — a health worker, a
   decision-maker, a judge — without a developer sitting beside them?
5. **Maintenance cost for the remaining schedule.** How much framework-specific work does
   it commit the team to, and can the team finish and document it in the time left?
6. **Dependency cost.** How many dependencies does it add, and how much of the
   *Dependencies and Data Management* rubric criterion does that put at risk?

## When a framework is chosen

A human makes the decision and records it here, at the top of this file, as a dated
decision. The repository changes at that point, in that same change:

- this lane gains its **own dependency manifest** (the framework's own file — a
  `pyproject.toml` or a `package.json`), and
- the root [`pyproject.toml`](../pyproject.toml) gains an explicit `tool.uv.workspace`
  exclusion, so a `uv sync` at the repository root does not try to resolve the new
  manifest as part of the root project.

Neither exists today, and **[`AGENTS.md`](AGENTS.md) forbids creating either in
advance**. A placeholder manifest would assert a decision that has not been made. The
repository's placeholder tests in `tests/test_placeholders.py` enforce exactly that, so a
future reader can tell the difference between "not decided yet" and "forgotten".

## Where to go next

- **Working in this lane** — the operative rules, including what must not be done here:
  [`AGENTS.md`](AGENTS.md). Read it before writing anything under `webapp/`.
- **Why this lane exists in this shape** — the deferred-decision record and the reasoning
  about a single root manifest: [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).
- **Before proposing any web work** — the repository-wide rules and lane map:
  [`AGENTS.md`](../AGENTS.md) at the root.
