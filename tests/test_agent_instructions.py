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


def test_root_agents_states_hard_prohibitions(repo_root: Path) -> None:
    content = (repo_root / "AGENTS.md").read_text(encoding="utf-8").lower()
    assert "no direct commits to main" in content or "never commit directly to `main`" in content
    assert "data/raw" in content


def test_firmware_agents_protects_vendored_code(repo_root: Path) -> None:
    """REQ-053."""
    content = (repo_root / "firmware/AGENTS.md").read_text(encoding="utf-8").lower()
    assert "lib/" in content
    assert "never" in content or "do not" in content
    assert "dataclass" in content or "circuitpython" in content


def test_webapp_agents_withholds_framework_decision(repo_root: Path) -> None:
    """An agent must not invent a framework that has not been chosen."""
    content = (repo_root / "webapp/AGENTS.md").read_text(encoding="utf-8").lower()
    assert "not been" in content or "no framework" in content or "undecided" in content
