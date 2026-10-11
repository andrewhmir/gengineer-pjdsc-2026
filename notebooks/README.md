# Notebooks

How analysis notebooks are named, written, guarded, and executed. This file carries the
lane's **conventions and mechanics**; [`AGENTS.md`](AGENTS.md) beside it carries the
**rules** and is binding for anything under `notebooks/`. Where the two cover the same
subject, this file explains and that file rules.

Notebooks are the analysis half of the data/analysis lane. They read the committed
synthetic fixtures in [`../data/samples/`](../data/samples/), so they run from a clean
clone on a laptop or in CI with no downloaded data and no network. Which data may be
committed at all is [`../docs/DATA.md`](../docs/DATA.md).

## Naming

    notebooks/NN-topic.ipynb

`NN` is a two-digit order prefix (`00-`, `01-`, `10-`) that fixes the reading order of
the analysis, and `topic` is a short lowercase kebab-case description of the question the
notebook answers: `03-immunization-coverage-trends.ipynb`. The prefix is what makes the
notebook directory read as a narrative rather than as a bag of files.

Two names are special:

| Name | Meaning |
|---|---|
| [`_template.ipynb`](_template.ipynb) | The starting point. Copy it, rename the copy, then edit the copy — never edit the template to fit one analysis. The leading underscore keeps it out of the numbered sequence. |
| `_*.ipynb` | Scratch. Not part of the narrative, never referenced by another notebook. |

The naming convention applies to the notebooks that are committed. An exploratory
notebook you are not ready to publish does not belong in this directory yet.

## What belongs in a notebook, and what does not

A notebook is **the analysis and its explanation, in the order a reader should meet
them**: the question, the data it reads, the steps taken, the numbers, and what those
numbers mean. Markdown cells carry the reasoning, so the notebook can be read by a judge
without running it.

A notebook is **not** a home for logic:

- **Logic a second notebook would need does not live in a cell.** Copy-pasted cells
  diverge silently, and nothing can test them. It goes in an importable module beside the
  notebooks, or in the lane that owns the logic — not into a `src/` package, which this
  repository deliberately does not have.
- **Nothing that only one cell needs is abstracted.** A notebook has exactly one caller,
  so functions used once are noise.
- **No secrets, no `data/raw/` reads, no network calls.** A committed notebook must be
  reproducible from a clean clone; see [`../docs/DATA.md`](../docs/DATA.md).
- **No stored outputs.** See below — this is the one mechanical rule that a hook enforces.

## Outputs: `nbstripout` and the commit hook

A committed output cell is a frozen screenshot of one machine's run: it bloats the clone,
it can leak whatever was in the dataframe, and a judge cannot reproduce it. The lane rule
is to keep every code cell's `outputs` list empty and its `execution_count` null **in the
file you commit**.

That rule is enforced in `.pre-commit-config.yaml` by the `nbstripout` hook, which
rewrites a staged notebook to remove outputs and execution counts before the commit is
recorded. Because `pre-commit run --all-files` cannot create its hook environments on the
maintainer's machine (a documented environment defect — see the root
[`../AGENTS.md`](../AGENTS.md)), `nbstripout` is also a dev dependency, so the same check
can be run directly:

```console
uv run nbstripout --verify notebooks/03-immunization-coverage-trends.ipynb
```

### `--verify` reports **any** change, not only stored output

`--verify` exits non-zero when the hook **would modify the file at all**. Stored output is
the usual cause and the one people look for, but it is not the only one. A newly
hand-authored notebook fails `--verify` while it has no outputs whatsoever, because
`nbstripout` rewrites every cell's `id` field to that cell's index number. A notebook
written by hand has random ids (`"id": "33ccc1fe"`) or none, so the file the hook would
write differs from the file on disk even though nothing was ever executed.

Measured on this repository:

| Template state | `uv run nbstripout --verify` |
|---|---|
| Hand-authored, random cell id, no outputs | exit 1 — `Dry run: would have stripped` |
| No `id` field at all | exit 1, plus a validation error |
| Hand-authored with `"id": "0"` on the first cell (id equals index) | exit 0 |
| After one `nbstripout` write pass | exit 0 |

**So the fix for a `--verify` failure is not necessarily "clear your outputs".** Run the
write pass once, review the diff, and commit the normalised file:

```console
uv run nbstripout notebooks/03-immunization-coverage-trends.ipynb
uv run nbstripout --verify notebooks/03-immunization-coverage-trends.ipynb   # now exit 0
```

Note the version skew: the dev dependency `nbstripout>=0.8` resolves to 0.9.1, while the
pre-commit hook pins `kynan/nbstripout` rev `0.7.1`. Both normalise cell ids to the index,
but they are not the same build, so a local `--verify` pass is strong evidence and not a
guarantee about the hook. Do not change either pin to "fix" the skew; it is a known,
accepted tradeoff.

## Execution: how notebooks are selected and run

`uv run pytest` does **not** execute notebooks. Execution happens only under the explicit
`--nbmake` flag.

**Location is the entire opt-in. There is no tag, marker, or metadata field that
selects a notebook.** `nbmake`'s collection predicate is:

```python
nbmake_enabled and p.match("*ipynb") and "_build" not in p.parts
```

It reads no notebook metadata at all. So **every `*.ipynb` directly in this directory is
executed** by Task 9's CI job, which runs:

```console
uv run pytest --nbmake notebooks/ -q
```

Run one notebook the same way:

```console
uv run pytest --nbmake notebooks/03-immunization-coverage-trends.ipynb -v
```

The practical consequence is the part worth remembering: **a half-written or scratch
notebook left in this lane will run in CI and can fail the build.** Being in `notebooks/`
is what gets it collected, and neither the `_template` underscore nor any metadata entry
excludes it — I verified that a `_`-prefixed notebook is collected exactly like any other.
Unfinished work therefore belongs **outside `notebooks/`** (or outside the repository), or
it must be self-contained enough to execute. The only exclusion `nbmake` applies of its own
accord is a path containing `_build`, which is its own convention for ignored build output,
not a general-purpose "do not run this" switch.

Because there is no opt-in marker, choosing to commit a notebook into this lane *is* the
decision to have it run in CI.

### The working directory is the notebook's own directory

The notebook executes with **the notebook's own directory as its working directory** —
`notebooks/`, not the repository root. `nbmake` sets the kernel's CWD to the notebook's
parent directory, so **every fixture path is written relative to the notebook**: from
`notebooks/` the committed samples are at `../data/samples/`, and the read is
`pd.read_csv("../data/samples/public_health_indicators.csv")`.

This is the one mechanic in this lane that looks like a bug when you get it wrong. A
repository-root path such as `data/samples/public_health_indicators.csv` fails under CI
with `FileNotFoundError`, naming a path that plainly exists at the repository root — it
resolved against `notebooks/`, not the root. Absolute paths (`C:\...`, `/Users/...`) are
ruled out for the same reason they are everywhere else: they are a dead end on every
other clone. Write the path relative to the notebook and both problems disappear.

### The CI job

Task 9 adds the workflow; until it lands, nothing runs these notebooks automatically. The
`notebooks` job, guarded on a pull request touching `notebooks/`, will run
`uv sync --locked` and then `uv run pytest --nbmake notebooks/ -q`. A failure in any cell
fails the build, so keep long-running work out of the template path, and prefer a
deterministic seed over a lucky one — an unseeded notebook passes on your machine and
fails on the judge's.

## Related documents

- [`AGENTS.md`](AGENTS.md) — the lane's hard rules; binding for everything in this directory.
- [`../docs/DATA.md`](../docs/DATA.md) — what data may be committed, and RA 10173.
- [`../docs/SOURCES.md`](../docs/SOURCES.md) — the citation every dataset needs, APA 7th Edition.
- [`../data/samples/README.md`](../data/samples/README.md) — the fixtures notebooks read.
