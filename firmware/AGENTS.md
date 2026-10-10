# AGENTS.md — firmware lane

Scope: everything under `firmware/`. The closest `AGENTS.md` wins, so this file
overrides the root [`AGENTS.md`](../AGENTS.md) for these paths; the root file's
repository-wide rules, commands, and environment constraints still apply and are not
repeated here.

This lane is **CircuitPython running on a microcontroller**, deployed by copying files
onto a USB mass-storage drive. That one fact drives every rule below.

## Hard rules

- **Never edit anything in `firmware/lib/`.** It is vendored third-party code, taken from
  the Adafruit CircuitPython bundle at a pinned version; the pin and the refresh
  procedure are recorded in the lane's `README.md`. To update it, re-copy from the bundle
  at the new pin. Do not hand-edit it, reformat it, or "fix" a lint or type finding
  inside it — if a tool complains about a vendored file, exclude the directory from the
  tool instead.
- **Never import from the repository root.** Not `data`, not `webapp`, not `tests`, not
  `docs`, not `specs`. `firmware/` is copied wholesale onto the board and the repository
  does not travel with it, so such an import works on a laptop and fails at boot — the
  worst possible failure mode, because it looks correct in review.
- **Keep the lane flat and dependency-free.** There is no packaging step and no
  installer. The lane is deployed by copying it onto the board, so a new first-party
  module is simply a **sibling of `code.py` at the firmware root** — that is what the
  board resolves, and it stays in the repository and in review scope.
- **Do not put first-party code in `firmware/lib/`.** `lib/` holds vendored Adafruit
  bundle code and nothing else, which is exactly why the read-only rule above exists. The
  read-only rule and this placement rule are one rule, not two.
- **Do not rename or replace `code.py`.** It is the CircuitPython auto-running entry
  point; the board executes it on boot. There is exactly one.

## CircuitPython is not CPython

The board runs CircuitPython: a small subset of the standard library plus the Adafruit
bundle. Code that is perfectly valid CPython can still crash at boot here, and CI cannot
catch all of it.

- **No `dataclasses`** — the module does not exist on CircuitPython.
- **No `match` statements.**
- **No `X | Y` type syntax** (PEP 604 unions), and no other construct newer than the
  pinned CircuitPython version supports.
- **Standard library plus the Adafruit bundle only.** No pip, no PyPI, no third-party
  import that is not vendored in `firmware/lib/`.
- Guard anything device-only, because it is absent off-device.

## Hardware seam

Hardware access goes behind a **seam** so that host-side tests can inject fakes. `board`,
`busio`, and `digitalio` do not exist off-device: importing them unguarded at module
scope makes the module unimportable on a laptop, which is where the tests run. Guard the
import, expose the result as a module-level flag, and keep the hardware-free path
meaningful so a test can assert on it.

## Verify before you claim

The CI workflow — not yet created by this bootstrap — is specified to byte-compile every
`firmware/**/*.py` (excluding `lib/`), to check that no firmware source imports a host-only
root module, and to check that `code.py` avoids the forbidden constructs above. Until it
exists, nothing validates this lane automatically.

**No check can prove the code runs on the board.** `py_compile` accepts code that still
crashes at boot, which is why the checks above are necessary but not sufficient. A human
must flash the board and watch it run before a firmware change is described as working.
Say "byte-compiles" when that is all that is known.

## Commands

```console
uv run pytest
uv run ruff format --check firmware/
uv run ruff check firmware/
```

The lane's own test module and its `README.md` — the flashing procedure, the pinned
bundle version, and the `code.py`/stdlib-`code` name collision — arrive with the lane
skeleton task, not with this file; until then `uv run pytest` is the whole gate.
Deploying is a copy, not a build: `code.py`, `lib/`, and a real `secrets.py` are copied
onto the board's `CIRCUITPY` drive.
