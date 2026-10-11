# `submission/` — the scored deliverables

This lane holds the artifacts the competition actually scores. Every other directory in the
repository feeds it: the notebook analysis, the firmware, and the web application exist so
that this lane can be handed to a judge. It is deliberately small — it records the limits,
the deadline, the deliverables, and the checklist. The deck PDF lands here; the video is
linked, not committed.

**Read the limits before planning any deck work.** They are hard, numeric, and penalised:
each slide and each 15 seconds over the limit costs a point.

## The three required deliverables

The final proposal is not one file. Each of the three below is required, and a missing one
is not a deduction — it is an incomplete entry.

| # | Deliverable | Form | Committed here? |
|---|---|---|---|
| 1 | **Slide deck** | PDF | **Yes**, once it is finalised — a deck PDF is small enough for the repository |
| 2 | **Demonstration video** | Recorded screen capture, **maximum 3 minutes** | **No** — linked, not committed (see [Why the video is linked, not committed](#why-the-video-is-linked-not-committed)) |
| 3 | **Code repository link** | The public URL below | Stated in this file and on the deck's final slide |

The repository link is <https://github.com/andrewhmir/gengineer-pjdsc-2026> — public, and the
same URL the root [`README.md`](../README.md) and [`CITATION.cff`](../CITATION.cff) publish.

## Hard limits and how they are penalised

| Deliverable | Limit | Deduction for exceeding it | Cap |
|---|---|---|---|
| Slide deck | **20 slides**, counting the title slide, the references, and any appendices | **1 point per 1–2 slides** beyond the limit | 10 points |
| Demonstration video | **3 minutes** of runtime | **1 point per 15 seconds** beyond the limit | 10 points |

Two consequences the team should not have to rediscover:

- The slide count includes the slides people usually leave out of the count. A 21-slide PDF
  is over the limit even though the extra slide is a references page, and 22 slides costs
  2 points.
- The video limit is in **time**, not file size or number of scenes. Three minutes and
  16 seconds is already 1 point.

The current numbers are recorded here and restated in the event primer, which is cited in
[`../docs/SOURCES.md`](../docs/SOURCES.md). If the organisers change a limit, the primer is
the authority and this table is corrected in the same change.

## Deadline

**Saturday 2026-10-24, 23:59** (Asia/Manila). The root [`README.md`](../README.md) records
the same date as "Final project due".

Work backwards from it: the deck is a PDF export rather than a live file, and the video needs
at least one full re-record after the last code change, so neither is a same-day task.

## What is scored, and where the evidence lives

The deck must let a judge check every criterion below without opening the repository.

| Criterion | Where the evidence is |
|---|---|
| Project Rationale and Design | The problem statement and the design decisions in the deck; [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) |
| Execution and Impact | The analysis outputs and what they change for a health worker |
| Code Repository | This repository: structure, documentation, reproducibility, dependencies, and data management |
| Demonstration Video | The linked video, within its limit |
| Technical Rigor and Innovation | The method, its limits, and what was rejected |
| Sources | [`../docs/SOURCES.md`](../docs/SOURCES.md) — **APA 7th Edition** |

**Sources are a separately scored criterion.** Every dataset and every external claim
appearing in the deck, in a figure, or in the video is cited in **APA 7th Edition** format in
[`../docs/SOURCES.md`](../docs/SOURCES.md), which is the single source of truth for
provenance. That file must be updated *before* a source is used, not after: a dataset that is
not listed there must not appear in the deck. Do not transcribe citations into the deck from
anywhere else, or the two copies will drift.

## Why the video is linked, not committed

**Decision: the demonstration video is linked from this file, not committed to the
repository.** No video binary is committed, and its hosted location is recorded in the
**Video link** section below.

The reason is the repository's size policy. A three-minute screen capture is hundreds of
megabytes, and [`../docs/DATA.md`](../docs/DATA.md) sets a hard limit of **no committed file
over 1 MB**; Git also keeps every version of a binary forever, so a re-recorded video would
bloat the history on every iteration rather than once. In a **public** repository that is a
permanent, irreversible size problem, and it would also put the *Dependencies and Data
Management* criterion at risk for an artifact that contributes nothing to it.

The slide deck PDF is treated the opposite way: it is a small text-heavy file that generates
a readable diff and stays far inside the 1 MB limit, so it **is** committed here once it is
final.

`tests/test_submission.py` asserts that nothing over 1 MB sits in this directory, so the
decision is enforced by the suite rather than by memory.

### Video link

**Not yet recorded — the link is added below when the video is published.**

- **Video URL:** _pending — add the host link here on the line below._
- **Access:** anyone with the link (a judge must not have to request permission).
- **Runtime:** record the exact runtime here, and check it against the 3-minute limit.

Keep the video file itself outside the repository (local disk, or the host's own storage);
only this link is committed.

## Pre-submission checklist

Run this in order before the deck is exported for the last time. Each line is a claim someone
has to be able to verify, not a reminder.

- [ ] **Slide count is 20 or fewer**, counted from the exported PDF including the title
      slide, the references, and the appendices.
- [ ] **Video runtime is 3:00 or less**, measured on the published file, with the exact
      runtime recorded in [Video link](#video-link) above.
- [ ] **Every source cited in APA 7th Edition** in
      [`../docs/SOURCES.md`](../docs/SOURCES.md), and every source in the deck appears there.
- [ ] **Deck PDF committed here**, with the repository link on its final slide.
- [ ] **Every scored criterion** in [What is scored](#what-is-scored-and-where-the-evidence-lives)
      has an explicit answer in the deck.
- [ ] **No secrets committed** — no `.env`, no `firmware/secrets.py`, no credentials or API
      tokens anywhere in the tree or in the history being pushed.
- [ ] **No data committed** — nothing under `data/raw/` or `data/interim/`, and no real
      patient or personally identifiable health data anywhere, per the Data Privacy Act of
      2012 (RA 10173). See [`../docs/DATA.md`](../docs/DATA.md).
- [ ] **README quickstart verified from a clean clone** — `git clone`, `uv sync`,
      `uv run pytest`, with no manual setup and no hardware attached.
- [ ] **CI green** on the commit being submitted.

The last three are the repository's own gates and are what a judge runs first; the root
[`README.md`](../README.md) documents the exact commands.

## Where to go next

- **What may be committed, and the size policy** — [`../docs/DATA.md`](../docs/DATA.md).
- **Citations and provenance** — [`../docs/SOURCES.md`](../docs/SOURCES.md).
- **Repository-wide rules and the lane map** — [`../AGENTS.md`](../AGENTS.md) and the root
  [`README.md`](../README.md).
