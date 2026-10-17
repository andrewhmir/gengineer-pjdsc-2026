# `webapp/` — Hinigram screening station

**Decision (2026-10-17): FastAPI + Jinja2 + vanilla JavaScript on canvas. One process, no Node
toolchain, no build step, no network at run time.** A human made this decision; the reasoning and
the rejected alternatives are in
[`../specs/2026-10-17-webapp-design.md`](../specs/2026-10-17-webapp-design.md) (§3). This lane is
no longer a placeholder: it is the screening station a person stands in front of.

The station asks one question per person. Someone steps onto the marked spot, presses **Start**,
stands still for thirty seconds, and reads one of three outcomes — *breathing looks regular*,
*irregular breathing — speak to the nurse*, or *reading not clear — try again* — with the
breathing rate behind it. Nothing is measured before Start, and nothing is stored.

## Quickstart

Requirements: [`uv`](https://docs.astral.sh/uv/) and Git, the same two the repository root needs.
No hardware: the station runs from a simulator.

```console
cd webapp
uv sync
uv run hinigram
```

That serves `http://127.0.0.1:8765`. Press **Start** and the station runs a full 33-second session
against the simulator: 3 s settle, 30 s capture, a result, then back to idle after 20 s or on
**Done**.

Commands:

| Command | Purpose |
|---|---|
| `cd webapp && uv sync` | Create or update the lane's `.venv` from `uv.lock`. |
| `cd webapp && uv run hinigram` | Serve the station on `127.0.0.1:8765` from the simulator. |
| `cd webapp && uv run hinigram --source replay` | Serve from the committed synthetic replay fixture. |
| `cd webapp && uv run hinigram --source serial --serial-port COM5` | Serve real frames from the receiver node. |
| `cd webapp && uv run pytest` | The lane suite: offline, deterministic, under 15 s. |
| `cd webapp && uv run ruff check .` | Lint. |
| `cd webapp && uv run mypy` | Type-check the package. |

The local gate before a push mirrors the root one:

```console
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

## Demonstrating the three outcomes

The simulator plays one scripted scenario per session. Choose it with the `scenario` query
parameter, or set the default with `--scenario`:

| Scenario | What the station shows |
|---|---|
| `regular` | Breathing looks regular · 15 br/min, steady |
| `watch` | Breathing looks regular · 22 br/min, worth a mention to staff |
| `tachypnea` | Irregular breathing · 26.4 br/min, flagged |
| `unsteady` | Irregular breathing · 16 br/min, unsteady rhythm |
| `apnea` | Irregular breathing · a breath pause of ten seconds or more |
| `motion` | Reading not clear · movement during the capture |
| `absent` | Settle finds no one breathing and returns to idle |

Open `http://127.0.0.1:8765/?scenario=tachypnea`, press Start, and the station produces a flagged
result after the capture. The parameter only changes what the simulator emits; it is ignored on
the replay and serial sources, and it never appears on the patient screen.

## What is deliberately absent

This build is the kiosk. The staff surfaces — the backend health graph, the recent-sessions table,
the phase-space torus, and the method page — are specified in the design record but not
implemented here. There is no database either: the station stores nothing at all, which is the
strongest reading of the privacy rule.

## Honest limits

- The detector is a **research prototype**. Its thresholds are prototype values configured in
  `hinigram/config.py`, not clinical ones, and it has not been validated against a person.
- The station has been exercised against the simulator and the replay fixture. The serial source
  is written and unit-tested with a fake stream, but **no receiver firmware exists yet**, so no
  real CSI frame has ever reached this code.
- No evaluation artifact exists, so the station makes no accuracy claim. When one is generated, it
  belongs on the method page with the rest of the numbers.
- There is no authentication. The server binds loopback precisely because it is a single-operator
  local prototype; a non-loopback `--host` prints a warning and asks you to think again.

## Working in this lane

The operative rules — module boundaries, what must not be added, and how patient copy is
tested — are in [`AGENTS.md`](AGENTS.md). The design record is
[`../specs/2026-10-17-webapp-design.md`](../specs/2026-10-17-webapp-design.md); the build plan it
came from is [`../specs/2026-10-17-webapp-kiosk-plan.md`](../specs/2026-10-17-webapp-kiosk-plan.md).
Repository-wide rules and the lane map are in [`../AGENTS.md`](../AGENTS.md), and the reasoning
about lane boundaries is in [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).
