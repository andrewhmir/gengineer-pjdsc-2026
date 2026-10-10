# Data Policy

What may and may not be committed to this repository, where the data comes from, and how
to get it. This document is the policy; `../data/README.md` is the
same policy in brief, next to the data it governs.

This repository is **public** and is a judged competition submission. The rubric scores
**Dependencies and Data Management**, and Philippine health data carries a legal
obligation independent of the rubric. Both point the same way: commit the structure and
the small fixtures, keep the bulk and anything personal out.

## The two rules

1. **Structure is committed; contents are not.** `data/raw/` and `data/interim/` are
   gitignored. A judge can read what the data is, where it came from, and how to fetch it;
   they cannot get a multi-gigabyte dump from a clone, and this repository never becomes a
   dumping ground.
2. **No real patient or personally identifiable health data may ever be committed.** See
   the section below; it is a legal obligation, not a style preference.

## What may and may not be committed

| Path | Committed? | What belongs there |
|---|---|---|
| `data/raw/` | **No** — gitignored, except its `README.md` | The full dataset exactly as downloaded, never modified. Immutable input. |
| `data/interim/` | **No** — gitignored, except its `README.md` | Intermediate, regenerable output of cleaning and joining. If it can be regenerated, it does not belong in Git. |
| `data/samples/` | **Yes** | Small, synthetic, illustrative fixtures. No real records. |
| `data/README.md`, `data/*/README.md` | **Yes** | The policy and the per-directory guidance. |
| `docs/SOURCES.md` | **Yes** | The citation and provenance record for every source. |
| Large binaries, model weights, `.zip`, `.parquet`, database dumps | **No** | Reference them from `SOURCES.md` and retrieve them by the documented procedure. |

The gitignore rules are in [`../.gitignore`](../.gitignore):

```gitignore
data/raw/*
!data/raw/README.md
data/interim/*
!data/interim/README.md
```

Note the shape: the rule ignores the **contents** of the directory, and the negated rule
re-admits the README. This keeps the directory in Git without a `.gitkeep`, because a
README carries real guidance while an empty placeholder cannot.

### Why `data/samples/` is committed

Two reasons, and both are scored:

- **Reproducibility.** `uv run pytest` and the notebooks must run from a clean clone with
  no dataset download, no credentials, and no network. Tests read fixtures from
  `data/samples/` and never touch `data/raw/`.
- **Judge-ability.** A judge opening the repository can see the expected data shape and
  run something immediately, rather than reading code that cannot execute.

Fixtures in `data/samples/` are **synthetic and illustrative**. They must be labelled as
such in `data/samples/README.md`, because a synthetic fixture mistaken for a real dataset
would mislead a judge. Keep each fixture small: a committed CSV stays in the tens of rows,
and no committed file may exceed 1 MB.

### Provenance is a precondition, not an afterthought

Every dataset must be added to [`SOURCES.md`](SOURCES.md) **before** it is used in
analysis. "Sources — reliable, up-to-date, APA 7th Edition" is a separately scored
criterion, and an uncited dataset is both a scoring risk and a reproducibility failure:
without the citation, nobody can re-derive the numbers. A notebook that reads a dataset
which is not in `SOURCES.md` is incomplete, even if it runs.

## Data privacy: RA 10173 (Data Privacy Act of 2012)

**No real patient data and no personally identifiable health data may ever be committed to
this repository.**

Public health data in the Philippines falls under the **Data Privacy Act of 2012
(Republic Act No. 10173)**. This repository is public, so a commit is not a private
mistake that can be quietly reverted — it is an irreversible disclosure. "It was only
there for two minutes" is not a defence; it was public, and it is in the history and in
every clone and fork.

Never commit, under any circumstances:

- names, addresses, dates of birth, or contact details of patients;
- PhilHealth numbers, hospital or patient record numbers, or any other national or
  institutional identifier;
- free-text clinical notes, which routinely contain identifying detail even when the
  structured columns do not;
- **any record that is unique enough to single a person out** — a rare diagnosis in a
  small barangay, an exact date of birth with a rare condition, a precise geolocation tied
  to one household. Aggregation is not anonymity if the cell size is one;
- credentials, tokens, or connection strings for a system that holds any of the above.

### Working with aggregate public health data

Aggregate statistics published by a government agency (for example the Department of
Health, the Philippine Statistics Authority, or the World Health Organization) are usable
**when they are already aggregate and public**, and they are the preferred source. Even
then:

- Cite the exact release in [`SOURCES.md`](SOURCES.md), including the version or
  extraction date, because these tables are revised over time.
- Record the retrieval date, since "up-to-date" is part of the scored criterion.
- Do not attempt to disaggregate or re-identify published aggregates, and do not join two
  datasets to produce small cells that were not published.
- If the licence or terms of use restrict redistribution, `data/raw/` plus the documented
  retrieval procedure is exactly how to stay compliant: the data is not redistributed.

If a task genuinely requires record-level data, that data stays **outside** this
repository, and only the aggregate result, the code, and the citation are committed. Raise
it with the maintainer first rather than deciding alone.

### If personal data is committed by accident

1. **Say so immediately.** Contact the maintainer ([@andrewhmir](https://github.com/andrewhmir))
   through a private channel, not a public issue. Alerting early is always better than
   hoping it is unnoticed; a public repository is indexed and cloned within minutes.
2. **Remove the file and rotate anything exposed.** Deleting it in a new commit does not
   remove it from history, so treat the data as disclosed and act accordingly.
3. **Expect history rewriting.** The commit must be purged from history
   (`git filter-repo --path <file> --invert-paths`), force-pushed, and every collaborator
   must re-clone. Coordinate before doing this; it invalidates everyone's local branch.
4. **Record the remediation** in [`../CHANGELOG.md`](../CHANGELOG.md) under `Security`,
   describing the class of data and the remediation, **never the data itself**.

See [`../SECURITY.md`](../SECURITY.md) for secret reporting and credential rotation.

## Retrieving the full datasets

The specific datasets are not yet chosen — that is a deferred decision, tracked in
[`../specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md) §9.
Once a dataset is chosen, its retrieval procedure is recorded here and its citation is
added to [`SOURCES.md`](SOURCES.md).

Until then, retrieve data manually and in the open, like this:

1. **Find the source** and open it in a browser. Prefer an official publisher (the
   Department of Health, the Philippine Statistics Authority, the World Health
   Organization, or a peer-reviewed data descriptor) over an aggregator or a scraped copy.
2. **Read the terms of use.** Note whether redistribution is permitted and whether an
   attribution requirement applies. If redistribution is restricted, the data must not be
   committed, and `data/raw/` plus this procedure is how the project stays compliant.
3. **Download it into `data/raw/`**, unmodified. Do not clean, rename, or subset it in
   place — `data/raw/` is immutable input, and `data/interim/` is where transformation
   output goes.
4. **Verify what you downloaded**: row count, column headers, the date range it covers,
   and the units. Record what you checked.
5. **Cite it in [`SOURCES.md`](SOURCES.md)**, in APA 7th Edition, with the retrieval date
   and the version or release you actually used.
6. **Confirm it is not committed.** Before you commit any code that reads it:

   ```console
   git status --porcelain
   git check-ignore -v data/raw/<file>
   ```

   `git status` must not list anything under `data/raw/`, and `git check-ignore` must
   report the file as ignored. The second command is the reliable one: a file that is
   ignored does not appear in `git status` at all.

When a dataset is settled and the retrieval becomes repetitive, a committed download
script replaces steps 1–4. That script belongs in the data lane and is worth its own
change; a script is reproducible in a way that a manual download is not, and the rubric
scores reproducibility. Do not commit the downloaded data alongside it.

## Size and format guidance

| Concern | Rule |
|---|---|
| Committed file size | **No committed file over 1 MB.** Enforced by the `check-added-large-files` pre-commit hook (`--maxkb=1024`), which is configured in [`.pre-commit-config.yaml`](../.pre-commit-config.yaml). Note that this hook **cannot currently run on the maintainer's machine** (see the known environment constraints in [`../AGENTS.md`](../AGENTS.md#known-environment-constraints)), so today the rule is enforced by review rather than by a gate that runs; a test-level check lands with the final verification task. |
| Sample fixtures | Tens of rows, not thousands. Small enough to read in a diff. |
| Notebook outputs | Stripped on commit by `nbstripout`; a committed notebook must not carry a large embedded table. |
| Data formats | Prefer text formats that diff well (CSV, JSONL) for fixtures. Minimise and document any binary format you must use. |
| Version control of data | Git only. DVC and Git LFS are deliberately **not** used; revisit if committed samples or model artefacts approach the size limits. |

## Related documents

- [`SOURCES.md`](SOURCES.md) — citations and provenance, APA 7th Edition.
- [`../SECURITY.md`](../SECURITY.md) — secrets, leak reporting, credential rotation.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how the data lane fits the three-lane model.
