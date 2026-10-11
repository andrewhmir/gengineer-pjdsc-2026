# AGENTS.md — notebooks lane

Scope: everything under `notebooks/`. The closest `AGENTS.md` wins, so this file
overrides the root [`AGENTS.md`](../AGENTS.md) for these paths; the root file's
repository-wide rules and commands still apply.

Notebooks are the analysis half of the data/analysis lane. They run on a laptop or in
CI, against committed synthetic samples. The data policy and the citation rule are in
[`docs/DATA.md`](../docs/DATA.md) and [`docs/SOURCES.md`](../docs/SOURCES.md); they are
binding here and are not restated.

## Hard rules

- **Clear outputs before committing.** Stored outputs bloat the clone, leak whatever was
  in the data, and cannot be reproduced by a judge — they are a frozen artifact of one
  machine's run. `nbstripout` enforces this on commit; keep every code cell's `outputs`
  empty and its `execution_count` null in the file you commit.
- **No absolute paths.** `C:\…` and `/Users/…` break for every other clone and for the
  judges. Read fixtures by a path relative to **the notebook**, for example
  `../data/samples/<name>.csv`.
- **Never read from `data/raw/` in a committed notebook or a committed output.**
  `data/raw/` is gitignored, local-only data; a notebook that depends on it is not
  reproducible from a clean clone.
- **Set deterministic seeds.** Sampling, train/test splits, and model initialisation all
  get an explicit seed, so the notebook produces the same result on a judge's machine.
- **Logic used by more than one notebook belongs in an importable module, not in a
  cell.** Copy-pasted cells diverge silently and cannot be tested. It goes in the lane
  that owns the logic, or beside the notebooks — not into a `src/` package, which this
  repository deliberately does not have.
- **Cite every dataset** in [`docs/SOURCES.md`](../docs/SOURCES.md) (APA 7th Edition)
  before it appears in a notebook, a figure, or the slide deck.

## Commands

```console
uv run pytest
uv run nbstripout --verify notebooks/<name>.ipynb
```

`--verify` exits non-zero for *any* change the commit-time hook would make, which is not
limited to stored output — the full semantics belong in the lane's `README.md`.

The lane's hygiene tests live in [`../tests/test_notebooks.py`](../tests/test_notebooks.py); run
them with `uv run pytest`. The suite does not execute notebooks. Under `--nbmake`, **every**
`*.ipynb` in this directory is executed — location is the only opt-in and there is no tag to drop —
so never leave a half-written or scratch notebook here expecting it to be skipped; the full
mechanics and the working-directory rule for fixture paths are in the lane's `README.md`.

## Notes

`data/samples/` holds the small synthetic fixtures that are committed. Real datasets are
retrieved per [`docs/DATA.md`](../docs/DATA.md) and never committed. Repository-level
prohibitions — including the ban on any real patient or personally identifiable health
data (RA 10173) — are in the root [`AGENTS.md`](../AGENTS.md).
