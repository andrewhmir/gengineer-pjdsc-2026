"""Data policy enforcement: the rubric scores data management, RA 10173 scores privacy."""

import subprocess
from pathlib import Path

import pytest

GITIGNORED_PATHS = (
    "data/raw/dataset.csv",
    "data/interim/step.csv",
    "firmware/secrets.py",
    ".env",
)
COMMITTED_DATA_FILES = (
    "data/README.md",
    "data/raw/README.md",
    "data/interim/README.md",
    "data/samples/README.md",
    "data/samples/public_health_indicators.csv",
)


def test_sensitive_paths_are_gitignored(repo_root: Path, tmp_path: Path) -> None:
    for relative in GITIGNORED_PATHS:
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{relative} is NOT gitignored"


@pytest.mark.parametrize("name", COMMITTED_DATA_FILES)
def test_committed_data_fixture_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing committed data file: {name}"


def test_data_tree_root_exists(repo_root: Path) -> None:
    """The data lane owns this assertion; it deliberately does not appear in Task 1."""
    assert (repo_root / "data").is_dir()


def test_sample_fixture_has_expected_schema(repo_root: Path) -> None:
    lines = (
        (repo_root / "data/samples/public_health_indicators.csv")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert lines, "sample fixture is empty"
    assert lines[0].strip() == "region,indicator,year,value"
    assert 2 <= len(lines) <= 50, "sample fixture must stay small; raw data does not belong in git"


def test_no_gitkeep_placeholders(repo_root: Path) -> None:
    """REQ-013: the tree is preserved with real README content, not empty placeholders."""
    assert not list(repo_root.rglob(".gitkeep"))
