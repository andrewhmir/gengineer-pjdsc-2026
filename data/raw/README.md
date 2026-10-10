# `data/raw/` — local-only raw data

Raw data is the dataset exactly as it was downloaded, before any cleaning, renaming,
subsetting, or joining. It is **immutable input**: never edit a file here in place,
because the analysis that produced a number must be able to point at the bytes it read.
Transformation output belongs in [`../interim/`](../interim/README.md).

## The contents of this directory are not committed

Every file here is **gitignored**, and it must stay that way. Only this `README.md` is
tracked: [`../../.gitignore`](../../.gitignore) ignores `data/raw/*` and re-admits the
negated `!data/raw/README.md`. A clone therefore carries the policy and the retrieval
procedure but never the data, which is also how the project stays compliant with a source
licence that forbids redistribution.

Before committing code that reads something placed here, confirm the data itself is not
staged:

```console
git status --porcelain
git check-ignore -v data/raw/<file>
```

`git status` must not list anything under `data/raw/`. The second command is the reliable
one, because an ignored file never appears in `git status` at all. If a data file does turn
up as tracked, stop and remove it from the index before continuing.

## How to fill it

Follow the retrieval procedure in
[`../../docs/DATA.md`](../../docs/DATA.md#retrieving-the-full-datasets): find an official
publisher, read the terms of use, download the file unmodified, verify what arrived (row
count, column headers, date range, units), then cite it in
[`../../docs/SOURCES.md`](../../docs/SOURCES.md) before any analysis uses it. A dataset that
is not cited in `SOURCES.md` may not be used, and a file here is not an exception.

## What must never be placed here

Never copy real patient records or any other personally identifiable health data into this
directory. **RA 10173** governs it, and a file here is not safe merely because it is
gitignored: it is read by notebooks, so it is also the shortest route into a committed
output. Record-level data that a task genuinely needs stays **outside** this repository,
and only the aggregate result, the code, and the citation are committed. The full
prohibition is in
[`../../docs/DATA.md`](../../docs/DATA.md#data-privacy-ra-10173-data-privacy-act-of-2012).
