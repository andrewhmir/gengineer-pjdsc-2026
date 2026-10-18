"""Agent instruction layer (REQ-050 to REQ-053).

Nested AGENTS.md files use nearest-file precedence, and shorter files are
followed more reliably, so length is asserted rather than merely encouraged.
"""

from pathlib import Path

import pytest

AGENTS_FILES = (
    "AGENTS.md",
    "firmware/AGENTS.md",
    "notebooks/AGENTS.md",
    "tests/AGENTS.md",
    "webapp/AGENTS.md",
)
MAX_AGENTS_LINES = 200


@pytest.mark.parametrize("name", AGENTS_FILES)
def test_agents_file_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing agent instructions: {name}"


@pytest.mark.parametrize("name", AGENTS_FILES)
def test_agents_file_is_within_line_budget(repo_root: Path, name: str) -> None:
    lines = (repo_root / name).read_text(encoding="utf-8").splitlines()
    assert len(lines) < MAX_AGENTS_LINES, (
        f"{name} is {len(lines)} lines; keep it under {MAX_AGENTS_LINES}"
    )


def test_claude_md_imports_agents_md(repo_root: Path) -> None:
    """REQ-052: a CLAUDE.md sibling makes AGENTS.md load in every session."""
    content = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in content


def test_root_agents_states_every_hard_prohibition(repo_root: Path) -> None:
    """One assertion per prohibition. Each literal is a rule-bearing phrase that
    occurs exactly once, so deleting that rule turns this red. Asserting a bare
    token (e.g. "data/raw") would not: the same words appear in the lane map and
    in the Lane reminders prose.
    """
    content = (repo_root / "AGENTS.md").read_text(encoding="utf-8").lower()
    assert "never commit directly to `main`" in content
    assert "never commit anything under `data/raw/` or `data/interim/`" in content
    assert "never commit `firmware/secrets.py` or `.env`" in content
    assert "10173" in content
    assert "never edit anything under `firmware/lib/`" in content


def test_firmware_agents_protects_vendored_code(repo_root: Path) -> None:
    """REQ-053. The vendored-read-only rule and the language subset are both needed."""
    content = (repo_root / "firmware/AGENTS.md").read_text(encoding="utf-8").lower()
    assert "never edit" in content and "lib/" in content
    assert "dataclasses" in content
    assert "match" in content


def test_webapp_agents_records_the_framework_decision(repo_root: Path) -> None:
    """The lane file must state the decision, not leave an agent to invent one."""
    content = (repo_root / "webapp/AGENTS.md").read_text(encoding="utf-8").lower()
    assert "fastapi" in content
    assert "no node" in content
