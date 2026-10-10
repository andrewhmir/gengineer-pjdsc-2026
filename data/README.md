# Data

Where this project's data lives and what may be committed. This file is the policy **in
brief**, next to the data it governs; [`../docs/DATA.md`](../docs/DATA.md) is the full
policy and the authority if the two ever disagree.

Public health analytics is the work, and this repository is **public** and **judged**: the
rubric scores *Dependencies and Data Management*, and Philippine health data carries a
legal obligation independent of the rubric. Both point the same way — commit the structure
and the small fixtures, keep the bulk and anything personal out.

## The three directories

| Directory | Committed? | What belongs there |
|---|---|---|
| [`raw/`](raw/README.md) | **No** — contents gitignored; only its `README.md` is committed | Data exactly as downloaded, never modified. Immutable input. |
| [`interim/`](interim/README.md) | **No** — contents gitignored; only its `README.md` is committed | Regenerable output of cleaning and joining. If it can be rebuilt, it does not belong in Git. |
| [`samples/`](samples/README.md) | **Yes** | Small, synthetic, illustrative fixtures that tests, notebooks, and judges run against. Never real records. |

The rules that keep it that way are the negated patterns in
[`../.gitignore`](../.gitignore): `data/raw/*` and `data/interim/*` ignore the *contents*
of a directory, and `!data/raw/README.md` / `!data/interim/README.md` re-admit the
README, so each directory stays in Git without a `.gitkeep`. A directory that must exist
gets a `README.md` that carries real guidance, never an empty placeholder.

## Where the full datasets come from

The datasets are **not chosen yet** — that is a deferred decision recorded in §9 of
[`../specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md).
Until they are, data is retrieved by the documented manual procedure in
[`../docs/DATA.md`](../docs/DATA.md#retrieving-the-full-datasets), which covers choosing
an official publisher, reading the terms of use, downloading unmodified into `raw/`,
verifying what arrived, and the citation step that must come before any analysis.

Every dataset is cited in [`../docs/SOURCES.md`](../docs/SOURCES.md) (APA 7th Edition)
**before** it is used. Large binaries, archives, and database dumps are never committed;
they are referenced from `SOURCES.md` and fetched by that procedure.

## Privacy: no real patient data, ever

**No real patient or personally identifiable health data may ever be committed to this
repository.** Public health data in the Philippines falls under the **Data Privacy Act of
2012 (RA 10173)**, and this repository is public, so a commit is an irreversible
disclosure rather than a private mistake that can be quietly reverted. The prohibition,
the list of what must never be committed, and the procedure if it happens anyway are in
[`../docs/DATA.md`](../docs/DATA.md#data-privacy-ra-10173-data-privacy-act-of-2012).
Read it before adding any data here.

## Related documents

- [`../docs/DATA.md`](../docs/DATA.md) — the full data policy, including RA 10173.
- [`../docs/SOURCES.md`](../docs/SOURCES.md) — citations and provenance, APA 7th Edition.
- [`../notebooks/AGENTS.md`](../notebooks/AGENTS.md) — how analysis code reads this data.
