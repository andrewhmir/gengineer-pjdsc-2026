# Sources

Provenance and citations for every dataset, statistic, document, and tool that this
project relies on. This file is the **single source of truth for sources**: if a dataset,
figure, or claim appears in a notebook, a chart, the slide deck, or the README, its source
is listed here.

**Citation format: APA 7th Edition** (*Publication Manual of the American Psychological
Association*, 7th ed.). "Sources — Reliable, up-to-date, APA 7th Edition" is a separately
scored criterion of this competition, assessed on the final proposal package and again in
the final round. A source that is not listed here does not exist as far as the submission
is concerned.

## How to use this file

- **Add a source before you use it**, not after. A notebook that reads an uncited dataset
  is incomplete even when it runs.
- **One entry per source**, under the right heading, in APA 7th Edition format.
- **Include a retrieval date** for anything that is not a fixed, versioned publication
  (websites, live tables, dashboards, repositories). Public health tables are revised
  silently, so the date you read them is part of the citation.
- **Label every placeholder.** Dataset templates are written in `[square brackets]` and
  must be completed before the entry is moved into the real list. A half-filled entry is
  worse than no entry, because it looks cited.
- **Prefer official, primary publishers**: the Department of Health (DOH), the Philippine
  Statistics Authority (PSA), the World Health Organization (WHO), and peer-reviewed data
  descriptors. An aggregator or a scraped mirror is a last resort and must be labelled as
  secondary.
- **Record the version you actually used.** A citation to "the PSA website" does not let
  anyone reproduce a number.

## Citation legend

| Kind of source | APA 7th pattern |
|---|---|
| Report by a group author | Organisation. (Year). *Title of report* (Report No. xxx). Publisher. URL |
| Web page | Organisation. (Year, Month Day). *Title of page*. Site name. URL |
| Dataset, versioned | Author, A. A. (Year). *Title of data set* (Version x.x) [Data set]. Publisher. DOI or URL |
| Journal article | Author, A. A., & Author, B. B. (Year). Title of article. *Journal Name, Volume*(Issue), pages. https://doi.org/xxxx |
| Software | Author, A. A. (Year). *Title of software* (Version x.x) [Computer software]. Publisher. URL |

The 7th edition differs from the 6th in the ways that most often matter here: up to 20
authors are listed in full; a DOI is given as a URL
(`https://doi.org/...`) with no "Retrieved from" and no database name; a publisher's
location is **not** given; and an organisation may be the author, so "DOH" is written out
in full as the author and omitted as the publisher when the two are the same.

## Sources currently used

### Competition and event sources

UP Data Science Society. (2026). *[PJDSC '26] Event primer content* [Event primer].
artemiui/pjdsc26-website. https://github.com/artemiui/pjdsc26-website/blob/main/event-mechanics-references/%5BPJDSC%20'26%5D%20Event%20Primer%20Content.md

This is the authoritative document for the competition's theme, topic list, mechanics,
rubric, and deliverables, and it is the source of the theme title, the ten official
topics, the 20-slide and 3-minute limits, the six judging criteria, and the event's
commitment to publish qualifying projects with citation to each contributing member. It
is a Markdown file in the event's website repository rather than a PDF, so the URL above
is the citable locator. A permanent copy of this file is **not** committed here; the
repository is the source of record. (Retrieved 10 October 2026.)

UP Data Science Society. (2026). *Philippine Junior Data Science Challenge 2026*.
https://github.com/artemiui/pjdsc26-website

The event's public website repository. Cited as the organisational source for the event
itself. (Retrieved 10 October 2026.)

### Privacy, ethics, and legal sources

Republic Act No. 10173. (2012). *An act protecting individual personal information in
information and communications systems in the government and the private sector, creating
for this purpose a National Privacy Commission, and for other purposes* (Data Privacy Act
of 2012). Official Gazette of the Republic of the Philippines.
https://www.officialgazette.gov.ph/2012/08/15/republic-act-no-10173/

The legal basis for the rule that no personally identifiable health data may be committed
to this repository. Discussed in [`DATA.md`](DATA.md) and [`../SECURITY.md`](../SECURITY.md).
(Retrieved 10 October 2026.)

National Privacy Commission. (2017). *Implementing rules and regulations of Republic Act
No. 10173, otherwise known as the Data Privacy Act of 2012*. Republic of the Philippines.
https://www.privacy.gov.ph/implementing-rules-and-regulations/

The implementing rules that operationalise the Act, including the principles for lawful
processing of personal data. (Retrieved 10 October 2026.)

### Tooling and standards sources

Astral. (2026). *uv* (Version 0.11.21) [Computer software].
https://github.com/astral-sh/uv

The package and environment manager that provides this project's one-command setup and its
committed lockfile. Cited because the repository's reproducibility rests on it.

Astral. (2026). *Ruff* (Version 0.17.0) [Computer software].
https://github.com/astral-sh/ruff

The linter and formatter. Pinned exactly, and the pin must match the `ruff-pre-commit`
revision in [`../.pre-commit-config.yaml`](../.pre-commit-config.yaml).

Python Software Foundation. (2026). *Python* (Version 3.12) [Computer software].
https://www.python.org/

The interpreter version this project pins in `.python-version` and `pyproject.toml`
(`requires-python = ">=3.12"`).

### Methodological sources

The following are the methodological standards this project intends to follow. They are
listed because the approach must be defensible, and each is cited again at the point of
use. They are not yet applied anywhere in the code.

American Psychological Association. (2020). *Publication manual of the American
Psychological Association* (7th ed.). https://doi.org/10.1037/0000165-000

The citation format mandated for this file and scored under the competition's "Sources"
criterion. The DOI above resolves to the 7th edition.

World Health Organization. (2024). *International statistical classification of diseases
and related health problems* (11th rev.). https://icd.who.int/

The standard classification for disease coding, to be used for any disease category named
in the analysis so that the terminology matches the source dataset. (Retrieved 10 October
2026.)

## Template for future dataset entries

Datasets are **not yet chosen** — see §9 of the deferred decisions in
[`../specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md).
Copy the appropriate template below, replace every `[bracketed placeholder]`, delete the
lines that do not apply, and move the completed entry into "Sources currently used" under
a new "### Datasets" heading. **Do not leave a placeholder in the used list.**

### Template A — agency dataset or published table

```text
[Authoring organisation, written out in full]. ([Year]). *[Title of data set or table]*
[Version or release identifier, if any] [Data set]. [Publisher, if different from the
author]. [DOI or URL]

Retrieved [Day Month Year], from [URL if the resource is not versioned].
Licence: [licence or terms of use]. Committed: no — retrieved by the procedure in
docs/DATA.md. [One sentence: what this dataset provides and which analysis uses it.]
```

A filled example of the shape (illustrative only — **this dataset is not used by this
project and must not be cited as if it were**):

> Philippine Statistics Authority. (2024). *Annual poverty indicators survey* [Data set].
> https://psa.gov.ph/
>
> Retrieved 10 October 2026. Licence: PSA open data, attribution required. Committed: no —
> retrieved by the procedure in `docs/DATA.md`. Provides household income bands used for
> the region-level correlation in notebook 02.

### Template B — versioned or archived dataset with a DOI

```text
[Author, A. A., & Author, B. B.]. ([Year]). *[Title of data set]* (Version [x.x])
[Data set]. [Publisher/Repository]. https://doi.org/[doi]

Licence: [licence, e.g. CC BY 4.0]. Committed: [no — retrieved by the procedure in
docs/DATA.md | no — licence forbids redistribution | yes, as a subset in
data/samples/<file>, because [reason]]. [One sentence on its use.]
```

### Template C — academic article describing or accompanying a dataset

```text
[Author, A. A., Author, B. B., & Author, C. C.]. ([Year]). [Title of article]. *[Journal
Name], [Volume]*([Issue]), [pages]. https://doi.org/[doi]

[One sentence: what the article establishes, and which of its data or methods this
project uses.]
```

### Template D — dashboard or interactive tool

```text
[Organisation]. ([Year, Month Day]). *[Title of dashboard]* [Interactive data dashboard].
[Site name]. [URL]

Retrieved [Day Month Year]. [One sentence: which figures were read from it and when,
because dashboards are updated in place and the numbers change.]
```

### Fields every dataset entry must record

| Field | Why it is required |
|---|---|
| Authoring organisation, full name | APA 7th uses the organisation as author; abbreviations must be introduced once and then used consistently. |
| Year (and Month Day for web content) | "Up-to-date" is part of the scored criterion; an undated source cannot be assessed for currency. |
| Title and version or release | Public health tables are revised silently; the version is what makes a number reproducible. |
| Publisher / repository | Distinguishes the publisher from the author, and locates the artefact. |
| DOI or URL | Locates it permanently. Prefer a DOI; DOI is written as a URL. |
| Retrieval date | Mandatory for anything that is not fixed and versioned. |
| Licence or terms of use | Determines whether the data may be committed, and what attribution is owed. |
| Committed: yes/no, and where | Keeps `data/` honest and keeps the repository inside the size policy. |
| One sentence on its use | Tells a judge and a future teammate which analysis depends on it. |

## Sources under consideration

Not yet used, and deliberately **not** cited as if they were. They are recorded so the same
ground is not re-researched twice. Nothing in this section may be relied on in an analysis
until it has been promoted to "Sources currently used".

| Candidate | Why it is interesting | Caveat |
|---|---|---|
| Department of Health Philippines disease surveillance reports | Primary, official, and the obvious anchor for a disease-surveillance topic. | Release cadence and machine-readability vary; check the licence before committing anything derived from it. |
| Philippine Statistics Authority census and vital statistics | Population denominators, which most rates need. | Published at a coarser geography and time resolution than clinical data; join keys must be checked. |
| World Health Organization Global Health Observatory | Comparable across countries, well documented, openly licensed. | Country-level only, so it cannot support a barangay-level claim. |
| OpenStreetMap and public facility registries | Support healthcare-access and service-delivery topics. | Coverage of health facilities in the Philippines is uneven; must not be presented as authoritative. |

## Related documents

- [`DATA.md`](DATA.md) — the data policy, including the RA 10173 prohibition and the
  retrieval procedure.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the official competition topic list this project
  must be framed against.
- [`../CITATION.cff`](../CITATION.cff) — how to cite this repository itself.
