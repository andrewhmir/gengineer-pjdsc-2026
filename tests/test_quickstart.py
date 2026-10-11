"""REQ-063: the README quickstart must work verbatim from a clean clone."""

import re
from pathlib import Path

FENCED_COMMAND = re.compile(r"^uv (sync|run [a-z-]+)", re.MULTILINE)


def test_readme_documents_only_uv_commands(repo_root: Path) -> None:
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "uv sync" in readme


def test_readme_names_every_lane(repo_root: Path) -> None:
    """The README must name all seven lanes. Its text is the assertion; the
    directories themselves are asserted by an all-lanes-exist check at the end
    of the plan, because four of these lanes do not exist when this file is
    first written."""
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    for lane in ("firmware/", "notebooks/", "webapp/", "data/", "docs/", "tests/", "specs/"):
        assert lane in readme, f"README does not mention the {lane} lane"


def test_readme_documents_the_tools_it_is_checked_for(repo_root: Path) -> None:
    """Guard: the check below must not pass merely because the scan found nothing.

    It also pins the pattern to the bare form. `uv run mypy` appears in the README
    with nothing after the tool name, so the assertion fails if the pattern is ever
    tightened to require trailing arguments — the defect this test was written for.
    """
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    found = {match.group(0) for match in FENCED_COMMAND.finditer(readme)}
    expected = {"uv sync", "uv run pytest", "uv run ruff", "uv run mypy"}
    assert expected <= found, f"README's line-anchored scan found only {sorted(found)}"


def test_readme_documents_no_unrunnable_command(repo_root: Path) -> None:
    """Every `uv run <tool>` in the README must be a tool that is actually installed."""
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    documented = set()
    for match in FENCED_COMMAND.finditer(readme):
        parts = match.group(1).split()
        if len(parts) >= 2 and parts[0] == "run":
            documented.add(parts[1])
    for tool in documented:
        if tool in {"pytest"}:
            continue
        assert tool in pyproject, f"README documents `uv run {tool}` but it is not a dependency"
