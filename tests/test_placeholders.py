"""Placeholder lanes must not pretend a decision has been made."""

from pathlib import Path


def test_webapp_readme_exists(repo_root: Path) -> None:
    assert (repo_root / "webapp/README.md").is_file()


def test_webapp_readme_defers_the_framework_decision(repo_root: Path) -> None:
    content = (repo_root / "webapp/README.md").read_text(encoding="utf-8").lower()
    assert "no framework" in content or "not been chosen" in content or "undecided" in content


def test_no_webapp_dependency_manifest_exists(repo_root: Path) -> None:
    """A placeholder pyproject.toml would be a lie about an unmade decision."""
    assert not (repo_root / "webapp/pyproject.toml").exists()
    assert not (repo_root / "webapp/package.json").exists()
