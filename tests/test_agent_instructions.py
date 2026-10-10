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
    """One assertion per prohibition, so deleting any single rule turns this red.

    An either/or phrase check would stay green if the secrets or RA 10173 rules
    were removed, which is the defect this test exists to prevent.
    """
    content = (repo_root / "AGENTS.md").read_text(encoding="utf-8").lower()
    assert "never commit directly to `main`" in content
    assert "data/raw" in content
    assert "data/interim" in content
    assert "firmware/secrets.py" in content
    assert ".env" in content
    assert "10173" in content
    assert "firmware/lib/" in content


def test_firmware_agents_protects_vendored_code(repo_root: Path) -> None:
    """REQ-053. The vendored-read-only rule and the language subset are both needed."""
    content = (repo_root / "firmware/AGENTS.md").read_text(encoding="utf-8").lower()
    assert "never edit" in content and "lib/" in content
    assert "dataclasses" in content
    assert "match" in content


def test_webapp_agents_withholds_framework_decision(repo_root: Path) -> None:
    """An agent must not invent a framework that has not been chosen."""
    content = (repo_root / "webapp/AGENTS.md").read_text(encoding="utf-8").lower()
    assert "no framework has been chosen" in content
