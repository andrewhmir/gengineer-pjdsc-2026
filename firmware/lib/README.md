# `firmware/lib/` — vendored third-party code

**This directory holds vendored Adafruit CircuitPython bundle code and nothing else.**
Everything here is third-party source copied in from the Adafruit CircuitPython Library
Bundle; none of it is ours.

## Rules

- **Never hand-edit a file in this directory.** Do not reformat it, do not "fix" a lint,
  format, or type finding inside it, and do not patch a vendored library in place. If a
  tool reports a finding here, exclude `firmware/lib/` from the tool in
  [`../../pyproject.toml`](../../pyproject.toml) instead. A local edit to vendored code is
  invisible to the next refresh and is lost the moment the directory is re-copied.
- **No first-party code belongs here.** Our own modules are **siblings of `code.py` at the
  firmware root** — that is the path the board resolves, and it stays in the repository and
  in review. Putting our code here hides it from review and contradicts the read-only rule
  above; the two rules are one rule.
- **Keep this directory minimal.** Copy only the libraries the node actually imports. The
  board's flash is small, and a full bundle buries the real dependency list.

## Pinned version

| Item | Value |
|---|---|
| Bundle release | `20261010` — [release page](https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/tag/20261010) |
| Asset | `adafruit-circuitpython-bundle-10.x-mpy-20261010.zip` |
| Variant | `10.x`, matched to the CircuitPython major version on the board |

The flashing procedure, the refresh steps for this directory, and the language subset the
lane is written against are in [`../README.md`](../README.md). Update this table, the one
there, and [`../../.env.example`](../../.env.example) together when the pin moves.

## What is not here yet

The bundle has not been copied in: no sensor code exists yet, so no library is imported and
none has been vendored. This file exists so the rule and the pin are recorded before the
first library lands, and so the empty directory is documented rather than kept with a
placeholder.

A CircuitPython board applies the same rule to this path: `.mpy` files compiled for a
different CircuitPython major version fail at import, which is why the variant in the table
above matters as much as the release date.
