# AGENTS.md — tests

Scope: everything under `tests/`. The closest `AGENTS.md` wins; see the root
`AGENTS.md` for repository-wide rules.

## Hard rules

- **No hardware and no network in tests.** These tests run on a laptop and in CI.
- **Never touch the real dataset.** Use fixtures from `data/samples/`.
- **Mock the board.** `board`, `busio`, and `digitalio` do not exist off-device;
  tests must inject fakes rather than importing them.
- **Fake the firmware seam, do not import it.** The hardware seam lives in `firmware/`
  precisely so these tests can inject fakes; the lane rules are in
  [`../firmware/AGENTS.md`](../firmware/AGENTS.md).
- Tests must pass with `uv run pytest` from a clean clone, with no manual setup.

## Commands

    uv run pytest              # full suite
    uv run pytest -v           # verbose
    uv run pytest tests/test_repo_smoke.py

## Notes

`repo_root` is a session-scoped fixture defined in `conftest.py`. Use it instead
of hard-coding paths or calling `os.getcwd()`.
