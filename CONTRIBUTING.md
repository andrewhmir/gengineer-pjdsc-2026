# Contributing to gengineer-pjdsc-2026

Thanks for working on this project. This repository is a **judged competition
submission** for PJDSC 2026, and the repository itself is scored on *Code Structure and
Documentation*, *Functional Execution and Reproducibility*, and *Dependencies and Data
Management*. That means the conventions below are not decoration — a tidy history and a
working quickstart are worth points.

By contributing you agree that your contribution is licensed under the
[Apache License 2.0](LICENSE), and that your name may be listed in
[`CITATION.cff`](CITATION.cff).

## Set up

```console
git clone https://github.com/andrewhmir/gengineer-pjdsc-2026.git
cd gengineer-pjdsc-2026
uv sync
uv run pytest
```

`uv` manages the Python interpreter, so you do not need Python 3.12 installed separately.
Bare `python` on this maintainer's machine is 3.10.11 — always go through `uv run …`.

## Branching

`main` is the default branch and is protected. **Nothing lands on `main` directly, not
even for the repository owner.** Every change goes on a branch and lands through a pull
request.

Branch names are lowercase and hyphenated, and the prefix names the lane:

| Prefix | Use for |
|---|---|
| `firmware/*` | CircuitPython for the sensor node. |
| `data/*` | Data acquisition, cleaning, and the data policy. |
| `notebooks/*` | Analysis notebooks. |
| `webapp/*` | The web application. |
| `docs/*` | Documentation and governance files. |
| `chore/*` | Tooling, CI, dependencies, repository hygiene. |
| `specs/*` | Design documents and plans. |

Examples: `firmware/dht22-reader`, `docs/setup-runbook`, `chore/pin-ruff`.

Work that spans lanes is allowed and encouraged: integration changes touch more than one
lane and should be reviewable in a single pull request. The pull request must then name
**every** lane it touches.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/), one logical change per
commit, with a lane scope:

```text
feat(firmware): add DHT22 temperature reader
fix(data): correct region name normalisation
docs(webapp): state that no framework has been chosen
chore(ci): gate firmware lane on py_compile
```

Useful types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`, `build`, `ci`.
Useful scopes: `firmware`, `data`, `notebooks`, `webapp`, `docs`, `tests`, `specs`,
`submission`, `ci`.

**House rule: no AI attribution trailers.** No `Co-Authored-By`, no "Generated with"
footer. Commits read as the human author's work. This is a deliberate choice for a judged
submission and is overridable by the maintainer.

## Pull requests

1. Branch off an up-to-date `main`.
2. Make the change, keeping the branch to one concern.
3. Run the gates below locally before you push.
4. Push, then open a pull request into `main` and fill in the template: **what** changed,
   **why**, **how it was verified**, and which **lanes** it touches.
5. Resolve review conversations and wait for `ci-success` to go green.
6. Merge. Linear history is required, so squash or rebase rather than creating a merge
   commit.

A pull request description is the record of *why* a change was made. Write it for a judge
who has never seen the branch.

### Gates

```console
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

`pre-commit run --all-files` is also configured and is the intended local gate, but it
**cannot run on the maintainer's current machine**: hook-environment creation fails with a
Windows virtualenv cache `WinError 5`. That is a known environment defect and not a
repository problem; until it is resolved, the four commands above plus CI are the
equivalent gates. Do not weaken `.pre-commit-config.yaml` to work around it.

### Review

A pull request needs approval before it merges **once more than one contributor exists**.
While the team has exactly one contributor, pull requests are self-reviewed: GitHub does
not let a pull request author approve their own pull request, so requiring an approval now
would leave `main` permanently unmergeable. The ruleset is therefore created *without* a
required-approval count, and **the approval requirement is enabled as the final step of
"Adding a teammate" below** — that is the first moment an eligible approver exists. The
exact command is recorded in [`docs/SETUP.md`](docs/SETUP.md).

## Adding a teammate

Three steps, in this order. The third is what makes the event's citation promise true.

1. **Invite them as a collaborator.**

   ```console
   gh api --method PUT repos/andrewhmir/gengineer-pjdsc-2026/collaborators/<handle> \
     -f permission=push
   ```

   On the web: *Settings → Collaborators and teams → Add people*.

2. **Add them to `.github/CODEOWNERS`** so that review requests route to them for the
   paths they own:

   ```text
   *       @andrewhmir @<handle>
   ```

3. **Add them to the `authors` list in [`CITATION.cff`](CITATION.cff)** with their given
   name, family name, and GitHub handle (`orcid` and `affiliation` if they want them).
   The event publishes qualifying repositories on UP DSSoc's official GitHub with proper
   citation to **each contributing team member**, so a contributor who is missing here is
   a contributor who is not cited.

Then, and only then, **enable the approval requirement** on the ruleset so that a second
person can review. The command that reads the current ruleset and writes it back with
`required_approving_review_count` set to 1, plus the read-back that verifies it, is in
[`docs/SETUP.md`](docs/SETUP.md#enabling-required-approvals).

Raising the count to 1 while the team still has one contributor will block every pull
request including your own — this is the single most common way to deadlock `main`.

Teammates must also be added to `.github/CODEOWNERS` before GitHub will offer them as a
reviewer.

## Working in the lanes

Each lane has an `AGENTS.md` describing the rules that apply to it. Read the one closest
to the file you are editing — the nearest file wins:

| Path | Scope |
|---|---|
| `AGENTS.md` | Repository-wide rules, commands, hard prohibitions. |
| `firmware/AGENTS.md` | CircuitPython subset, `CIRCUITPY` deploy model, vendored `lib/`. |
| `notebooks/AGENTS.md` | Output stripping, no absolute paths, deterministic seeds. |
| [`tests/AGENTS.md`](tests/AGENTS.md) | No hardware, no network, mock the board, use `data/samples/`. |
| `webapp/AGENTS.md` | The framework is undecided; do not invent one. |

Those files are operational and deliberately do not repeat this document. Where they
overlap, they point here. A path above that is not yet a link belongs to a lane the
bootstrap has assigned rules to but not yet created; each lane task adds its file.

## Hard rules

- **Never commit to `main` directly.**
- **Never commit anything under `data/raw/` or `data/interim/`** — see
  [`docs/DATA.md`](docs/DATA.md).
- **Never commit `firmware/secrets.py` or `.env`.** Commit
  `firmware/secrets.example.py` and `.env.example` instead.
- **Never commit real patient or personally identifiable health data.** Data Privacy Act
  of 2012 (RA 10173).
- **Never edit anything in `firmware/lib/`** — it is vendored third-party code.
- **No AI attribution trailers.**
- **All repository content is in English**, including code comments, notebook prose, commit
  messages, and issues.
