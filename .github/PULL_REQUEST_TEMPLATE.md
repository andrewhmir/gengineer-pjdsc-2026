<!--
One concern per pull request. The lane map and the branch/commit conventions are in
../CONTRIBUTING.md; do not restate them here.
-->

## What

<!-- What changed, in a sentence or two. Name the files or directories a reviewer should look at. -->

## Why

<!-- The problem this solves, or the decision it implements. Link the issue if one exists. -->

## Lane(s) touched

<!--
Name every lane this pull request touches: firmware, data, notebooks, webapp.
Cross-cutting paths (tests, docs, specs, .github) are not a lane — say "no lane" when
only those change.
An integration pull request that spans lanes must name every lane it touches; a
reviewer cannot infer the second lane from the first diff hunk.
-->

## How this was verified

<!--
Evidence, not a claim. Paste the command and what it printed, for example:

    uv run pytest -q              -> 89 passed
    uv run ruff format --check .  -> no files to reformat
-->

## Checklist

- [ ] `uv run pytest` passes.
- [ ] `uv run ruff format --check .` reports no files to reformat and `uv run ruff check .` is clean.
- [ ] No secret, credential, or real patient or personally identifiable health data is included.
- [ ] Nothing under `data/raw/` or `data/interim/` is committed.
- [ ] Documentation updated where this change makes a documented claim untrue.
