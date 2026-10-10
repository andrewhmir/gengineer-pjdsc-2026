# `data/interim/` — local-only intermediate data

Intermediate data is the output of cleaning, joining, reshaping, and feature-building: the
step between [`../raw/`](../raw/README.md) and the tables an analysis actually reads. It is
**regenerable by definition** — every file here can be rebuilt from `raw/` plus the
committed code — and that is precisely why none of it is committed.

## The contents of this directory are not committed

Every file here is **gitignored**; only this `README.md` is tracked.
[`../../.gitignore`](../../.gitignore) ignores `data/interim/*` and re-admits the negated
`!data/interim/README.md`, so the directory survives in Git without a `.gitkeep`.

Keeping regenerable output out of Git costs nothing and buys two things:

- **A small repository.** A judge clones megabytes, not a working directory full of
  half-processed copies of the dataset.
- **No stale results.** A committed intermediate is a frozen artifact of one machine's run,
  and it can silently disagree with the code that claims to produce it. Nothing here is a
  source of truth; if a file disagrees with the code, delete it and regenerate it.

## Working here

- **Name a file after the step that produces it** (for example
  `01_indicators_deduplicated.csv`), so the order of the pipeline can be read off the
  directory without opening anything.
- **Keep the producing step committed and runnable.** A file here with no script or
  notebook that regenerates it does not belong here; it belongs in `raw/`, or it should be
  deleted. A clean clone must be able to rebuild this directory from scratch.
- **Never treat a file here as an input to a committed notebook's stored output.** CI runs
  from a clean clone where this directory is empty, so anything an analysis depends on is
  built by the committed code or read from [`../samples/`](../samples/README.md).

Real patient or personally identifiable health data must never be copied into this
directory either: intermediate does not mean anonymous. **RA 10173** and the full
prohibition are in
[`../../docs/DATA.md`](../../docs/DATA.md#data-privacy-ra-10173-data-privacy-act-of-2012).
