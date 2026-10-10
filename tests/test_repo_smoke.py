"""Bootstrap invariants for the repository scaffold.

These are genuine assertions: they fail if a lane is removed, the Python pin
is lost, or the secret-scanning configuration disappears.
"""

import sys
from pathlib import Path

import pytest

REQUIRED_ROOT_FILES = (
    "pyproject.toml",
    ".python-version",
    ".gitignore",
    ".gitleaks.toml",
    ".pre-commit-config.yaml",
    ".editorconfig",
)
REQUIRED_ROOT_DIRS = ("tests",)


@pytest.mark.parametrize("name", REQUIRED_ROOT_FILES)
def test_required_root_file_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing required root file: {name}"


@pytest.mark.parametrize("name", REQUIRED_ROOT_DIRS)
def test_required_root_dir_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_dir(), f"missing required root directory: {name}"


def test_python_version_pin_is_consistent(repo_root: Path) -> None:
    """REQ-022: .python-version and requires-python must agree."""
    pin = (repo_root / ".python-version").read_text(encoding="utf-8").strip()
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    assert pin.startswith("3.12"), f"unexpected pin: {pin!r}"
    assert 'requires-python = ">=3.12"' in pyproject


def test_supported_python_floor_is_enforced() -> None:
    assert sys.version_info >= (3, 12), "run the suite with Python 3.12 or newer"


def test_gitignore_has_no_trailing_comments(repo_root: Path) -> None:
    """A trailing comment turns a pattern into a never-matching literal."""
    offenders = [
        line
        for line in (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "#" in line
    ]
    assert not offenders, f"trailing comments on .gitignore patterns: {offenders}"
