# `data/samples/` — committed synthetic fixtures

Small fixtures that **are** committed, so the project runs from a clean clone with no
dataset download, no credentials, and no network. They exist for the two purposes the
rubric scores:

- **Reproducibility.** `uv run pytest` and the committed notebooks read fixtures from here,
  so a judge can run something immediately instead of reading code that cannot execute.
- **Judge-ability.** The expected shape of the data is visible in the repository, in a
  diff a human can actually read.

Everything in this directory is deliberately tiny. The full datasets are retrieved per
[`../../docs/DATA.md`](../../docs/DATA.md) and are never committed.

## Every fixture here is synthetic and illustrative

**No file in this directory is a real dataset, and no value in one is a real measurement.**
The fixtures are fabricated for this repository to exercise code: the rows are invented,
the values are made up, and the regions are not real administrative regions. They are
labelled as fabricated here, and — where a column can carry it — inside the fixture itself,
so that a copied row cannot be mistaken for a genuine statistic.

Two rules follow, and neither is negotiable:

- **Do not present a fixture as data.** Nothing here may be cited as a source, quoted in
  the slide deck, or reported as a finding. A synthetic fixture mistaken for a real dataset
  would mislead a judge, which is worse than having no fixture at all.
- **Never build a fixture from real records.** A fixture is not made more realistic by
  copying real rows and truncating them. **No real patient or personally identifiable
  health data may ever be committed to this repository** — RA 10173 (Data Privacy Act of
  2012) makes that a legal obligation, not a style preference. Truncated, hashed, or
  "de-identified" extracts of real records are still real records, and aggregation is not
  anonymity if a cell describes one person. See
  [`../../docs/DATA.md`](../../docs/DATA.md#data-privacy-ra-10173-data-privacy-act-of-2012).

## Size ceiling

| Concern | Rule |
|---|---|
| Rows per fixture | Tens of rows, not thousands. Small enough to read in a diff during review. |
| File size | **No committed file may exceed 1 MB.** Fixtures are kilobytes; a fixture approaching the limit has stopped being a fixture and become a dataset. |
| Format | Prefer text formats that diff well (CSV, JSONL). Minimise and document any binary format, and justify it in the fixture's entry below. |
| Column contract | Fix the columns once and keep them fixed. Downstream tests, notebooks, and CI depend on the exact header, so a fixture is changed only together with the code that reads it. |

## Provenance

Real datasets are cited in [`../../docs/SOURCES.md`](../../docs/SOURCES.md) in APA 7th
Edition **before** they are used; that is the rule in
[`../../docs/DATA.md`](../../docs/DATA.md) and it is binding on analysis, not on fixtures.

A synthetic fixture is the one entry in this repository with **no source to cite**: it was
invented here, so it gets no entry in `SOURCES.md` and must never be listed there as if it
were data. The provenance record for a fixture is instead:

1. the statement in this file that it is fabricated, and
2. the note under its heading below, naming what was invented and why.

That is what REQ-034 asks for when it requires "a committed sample plus provenance": for a
synthetic file, the honest provenance is the declaration that it has no external origin.

## Fixtures

### `public_health_indicators.csv`

Column contract — the header is exactly `region,indicator,year,value`:

| Column | Type | Meaning |
|---|---|---|
| `region` | text | The reporting area. Every value here is an **invented** place name and carries a `(fictional)` marker, so the fabrication is visible even in a single copied row. |
| `indicator` | text | The public-health measure, with its unit in the name, for example `Childhood immunization coverage (percent)`. |
| `year` | integer | The reference year of the value. |
| `value` | decimal | The reported figure, in the unit named by `indicator`. |

Provenance: **fabricated for this repository**. The regions do not exist, the values were
written by hand to be plausible in shape and are not measurements from any survey, and
there is no underlying dataset — this file is not a subset, a sample, or an anonymised
extract of any source. It is read by the test suite and by the notebook template in
[`../../notebooks/`](../../notebooks/) so that both can run without the real data.
