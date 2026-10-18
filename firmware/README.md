# !!!! Request to MODIFY this since we will NOT be using CircuitPython for this project

# Firmware lane — CircuitPython sensor node

This lane is the sensor node half of the project. It is **CircuitPython running on a
microcontroller**, and it is deployed by **copying files onto a USB mass-storage drive**.
There is no build, no installer, and no packaging step.

Rules that bind this lane, and the reasons behind them, are in
[`AGENTS.md`](AGENTS.md) — read it before changing anything here. The design rationale is
in [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## What is here today

| File | Role |
|---|---|
| `code.py` | The auto-running entry point. The board executes it on boot. There is exactly one, and it is never renamed. |
| `lib/` | Vendored Adafruit bundle code only. Never hand-edited; see [`lib/README.md`](lib/README.md). |
| `secrets.example.py` | Committed template for the gitignored `secrets.py`. Placeholders only. |
| `config.example.toml` | Documentation of the configuration keys. Not parsed by the firmware. |

No sensor or network code exists yet. `code.py` currently reports node status through a
hardware-free check path, and is the seam that host-side tests assert on. Do not read more
capability into it than that: it has been byte-compiled in CI and flashed by nobody.

## Deploy: copying onto the board

CircuitPython boards expose their flash as a USB mass-storage drive named `CIRCUITPY`. The
board runs `code.py` from the root of that drive every time it boots or resets, and the lane
is laid out flat so that the drive resolves it exactly as the repository does.

1. Connect the board. A drive named `CIRCUITPY` appears.
2. Copy the three things the board needs — `code.py`, `lib/`, and the real `secrets.py`
   from step 3 — onto the drive, preserving layout. Nothing else in this directory has to
   travel: the board never reads `secrets.example.py` or `config.example.toml`, and the
   host-side checks leave a `__pycache__/` behind that would otherwise ride along onto the
   drive.

   ```console
   cp firmware/code.py /path/to/CIRCUITPY/code.py
   cp -r firmware/lib /path/to/CIRCUITPY/lib
   ```

   On Windows the drive is a letter, for example `E:\`, and these are ordinary file
   copies; there is no `make`, no upload step, and no serial tool involved.

3. Create the real credentials file **on the drive, and only there**:

   ```console
   cp firmware/secrets.example.py /path/to/CIRCUITPY/secrets.py
   ```

   Then edit the copy and replace every placeholder with the real value. `secrets.py` is
   gitignored (see [`.gitignore`](.gitignore)) and must never be committed, printed, or
   pasted into an issue. The template's keys are documented in
   [`secrets.example.py`](secrets.example.py).

4. Watch the serial console (or open `code.py` in a CircuitPython-compatible editor) to
   confirm the board booted and ran `code.py` to the end of its top level.

**Flashing is how a firmware change is verified.** Everything else in this file describes
what a machine can check without the board, which is strictly less.

## Host-side checks (no hardware needed)

These run on a laptop and in CI, against the repository's Python 3.12 toolchain:

```console
uv run pytest tests/test_firmware.py -v
uv run ruff format --check firmware/
uv run ruff check firmware/
```

The lane's test module checks three ways a CircuitPython program fails at boot:

- every `firmware/**/*.py` outside `lib/` **byte-compiles**;
- `code.py` avoids constructs CircuitPython does not have;
- no firmware source imports a host-only repository root module such as `tests` or
  `data`, which would work on a laptop and fail at boot on the board.

It also imports `code.py` off-device, which is what makes the guarded hardware import
load-bearing.

### CI proves byte-compilation only

**CI verifies byte-compilation and structure. It cannot verify on-device behaviour.**
`py_compile` accepts code that still crashes at boot: a missing module on the board, a
sensor that is not wired, an API that changed, or a construct CircuitPython lacks all pass
a byte-compile and fail on hardware. A human must flash the board and watch it run before a
firmware change is described as working. When only the checks above have run, the honest
description is "byte-compiles", not "works".

The same limit applies to the other cross-cutting suites: `uv run pytest` must pass from a
clean clone with **no hardware attached and no network access**, so nothing here may depend
on a board being present.

### `code.py` collides with the standard library's `code` module

`code.py` is a required CircuitPython entry-point name, and it is also the name of a module
in CPython's standard library. Putting `firmware/` on `sys.path` to test it would shadow
`code` for everything else imported in that session, which produces confusing failures far
from the cause.

`tests/test_firmware.py` therefore loads the file **by path** with
`importlib.util.spec_from_file_location("firmware_code", …)` under an isolated module name,
and never adds `firmware/` to `sys.path`. Do not "fix" the collision by renaming `code.py`,
and do not add `firmware/` to `[tool.pytest.ini_options] pythonpath`.

## Pinned Adafruit CircuitPython bundle

`firmware/lib/` is populated from the Adafruit CircuitPython Library Bundle, pinned to one
dated release so that the board and the repository hold the same code:

| Item | Value |
|---|---|
| Bundle release | `20261010` — [adafruit/Adafruit_CircuitPython_Bundle `20261010`](https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/tag/20261010) |
| Download | `adafruit-circuitpython-bundle-10.x-mpy-20261010.zip` |
| Variant | `10.x` — the documented default; see below |

The pin uses the `10.x` bundle, which is the documented default because the board has not
been chosen yet and no CircuitPython major version is recorded in this repository. **If the
team's board runs a different CircuitPython major version, download that major version's
asset from the same release page** — a mismatched bundle fails at import time and looks like
a code bug. The same pin is recorded as `CIRCUITPY_BUNDLE_VERSION` in
[`../.env.example`](../.env.example), so all three carriers move together.

### Refreshing `lib/`

1. Download the pinned zip from the release page above (or the newer release you are
   moving to).
2. Unzip it. Copy **only the libraries the node actually uses** from
   `adafruit-circuitpython-bundle-10.x-mpy-20261010/lib/` into `firmware/lib/`. Copying the
   whole bundle wastes the board's flash and buries the real dependency list.
3. Record the change: update the pin in the table above, in
   [`lib/README.md`](lib/README.md), and in [`../.env.example`](../.env.example), and add a
   [`../CHANGELOG.md`](../CHANGELOG.md) entry naming the old and new pins.
4. Never edit a vendored file to satisfy a linter, a formatter, or a type checker. If a
   tool reports a finding inside `firmware/lib/`, exclude the directory from the tool in
   [`../pyproject.toml`](../pyproject.toml). Re-apply the finding as a note here or report
   it upstream instead.

## The CircuitPython language subset

CircuitPython is not CPython. Only the CircuitPython standard library and the modules
vendored in `lib/` exist on the device.

- **No `dataclasses`** — the module does not exist.
- **No `match` statements.**
- **No `X | Y` type syntax** (PEP 604 unions), and nothing else newer than the pinned
  CircuitPython supports. Prefer plain code over clever annotations.
- **Standard library plus the Adafruit bundle only.** No `pip`, no PyPI, no dependency that
  is not vendored in `lib/`.
- **Guard everything device-only.** `board`, `busio`, and `digitalio` do not exist
  off-device, so importing them unguarded at module scope makes the module unimportable on
  a laptop. Import them inside a guard that sets a module-level availability flag, and keep
  the hardware-free path real enough to test.
- **Never import from the repository root.** `firmware/` is copied out of the repository
  and onto the board; the repository does not travel with it.

## Where new first-party code goes

A new first-party module is a **sibling of `code.py` at the firmware root**, because that
is what the board resolves and what stays in review scope. `lib/` is only for vendored
Adafruit bundle code, so nothing of ours is ever placed there.
