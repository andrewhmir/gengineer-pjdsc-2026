# Security Policy

This repository is **public** and is a judged competition submission. Two risks matter
here: a leaked credential (most often WiFi credentials pasted into firmware) and the
accidental publication of personal health data.

## Supported versions

Nothing here is released yet. The project is in bootstrap; the only branch receiving
changes is `main`, and it receives them through pull requests.

## No secrets in the repository

Nothing that grants access to anything belongs in Git history, ever — once pushed, a
secret is public even if a later commit deletes it.

| Never committed | Committed template |
|---|---|
| `firmware/secrets.py` | `firmware/secrets.example.py` (lands with the firmware lane) |
| `.env` | [`.env.example`](.env.example) |

Both real files are listed in [`.gitignore`](.gitignore). The templates contain placeholder
keys only, with no real values, and exist so that a contributor can copy one and fill it
in locally. `.env.example` is present now; `firmware/secrets.example.py` arrives with the
firmware lane, so the first line below only works once that lane has landed:

```console
cp firmware/secrets.example.py firmware/secrets.py   # after the firmware lane lands
cp .env.example .env
```

If you are about to commit a WiFi SSID, a password, an API token, a database URL, or a
service-account key: stop. Put it in `firmware/secrets.py` or `.env` instead.

## How secret scanning actually runs

**Secret scanning runs as the `secrets` CI job, not as a pre-commit hook.** The `secrets`
job installs the free gitleaks CLI and runs it against this repository's configuration on
every push and pull request:

```console
gitleaks detect --config .gitleaks.toml --redact -v
```

`--redact` prevents a real finding from being printed into a build log in cleartext, and
[`.gitleaks.toml`](.gitleaks.toml) allowlists only the three files that are *supposed* to
contain placeholder-shaped strings: `firmware/secrets.example.py`, `.env.example`, and
`docs/SETUP.md` (whose copy-paste commands contain placeholder tokens). Keep those
filenames as they are; renaming a file without updating `.gitleaks.toml` would turn a
deliberately narrow allowlist into dead configuration.

**Why not a pre-commit hook?** The upstream gitleaks pre-commit hook is declared with
`language: golang`, so pre-commit would build or fetch a Go toolchain just to run it. This
project does not depend on Go, and adding that hook would make `pre-commit run --all-files`
unrunnable on any machine without a Go toolchain — turning a security check into a reason
people stop running their local gates at all. The CI job is the backstop, and it cannot be
skipped by forgetting to install hooks. Do **not** add a local gitleaks hook expecting it
to work.

If you add a new file that legitimately contains placeholder-shaped strings, add a narrow
path pattern to the `[allowlist]` in `.gitleaks.toml` and say why in the pull request. Do
not disable the default rule set.

## Reporting a leak or a vulnerability

Do not open a public issue for a live secret or an exploitable vulnerability — that
publishes it.

1. **Report privately**, either through GitHub's *Security → Report a vulnerability*
   advisory form on this repository, or by contacting the maintainer
   ([@andrewhmir](https://github.com/andrewhmir)) directly.
2. Include what you found, where (file and commit if known), and how it could be abused.
   Do not include the secret's value in the report if you can avoid it.
3. The maintainer acknowledges within a few days and tells you what happens next.

## Rotating a compromised credential

Assume anything that reached a commit is compromised. Deleting the file is **not**
enough — it stays in history, so rotate the credential itself.

1. **Revoke and reissue** the credential at its source: regenerate the API token, change
   the WiFi password, rotate the database password, or delete and re-create the key pair.
2. **Move the new value out of Git**: put it in `firmware/secrets.py` or `.env`, which are
   both gitignored.
3. **Remove it from history** if it was pushed. Rewriting public history is disruptive and
   breaks everyone's clones, so coordinate first; prefer rotation, and treat history
   rewriting as a follow-up:
   `git filter-repo --path <file> --invert-paths`, then force-push and tell collaborators
   to re-clone.
4. **Record what happened**, without the value: a `Security` entry in
   [`CHANGELOG.md`](CHANGELOG.md) and, if it was in a released artifact, a note in the
   pull request. Do not write the secret into the changelog.
5. **Verify**: re-run the scanner locally against the working tree and confirm the `secrets`
   CI job is green on the next push.

## Personal health data

**No real patient or personally identifiable health data may ever be committed to this
repository.** Public health data in the Philippines is covered by the **Data Privacy Act
of 2012 (Republic Act No. 10173)**, and this repository is public: committing such data
would be an irreversible disclosure, not just a mistake.

- `data/raw/` and `data/interim/` are gitignored. Nothing there is committed.
- `data/samples/` holds small **synthetic, illustrative** fixtures only, and they are
  labelled as such.
- Any dataset that is de-identified must still be checked for re-identification risk
  before it is used, and cited in [`docs/SOURCES.md`](docs/SOURCES.md).

The full data policy is in [`docs/DATA.md`](docs/DATA.md). Read it before adding data.
