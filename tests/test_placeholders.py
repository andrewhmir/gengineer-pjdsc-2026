"""Placeholder lanes must not pretend a decision has been made."""

from pathlib import Path


def test_webapp_readme_exists(repo_root: Path) -> None:
    assert (repo_root / "webapp/README.md").is_file()


def test_webapp_readme_defers_the_framework_decision(repo_root: Path) -> None:
    content = (repo_root / "webapp/README.md").read_text(encoding="utf-8").lower()
    assert "no framework" in content or "not been chosen" in content or "undecided" in content


def test_webapp_contains_nothing_but_the_placeholder_documents(repo_root: Path) -> None:
    """Assert the lane's directory SHAPE, not a list of forbidden filenames.

    The lane rule forbids a dependency manifest, but naming `pyproject.toml` and
    `package.json` alone leaves `requirements.txt`, a lockfile, and any scaffolded
    framework tree unnoticed: a teammate choosing Flask via `requirements.txt` would
    keep the suite green while breaking the invariant. Asserting the whole directory
    contents is stronger and also catches scaffolding and stray configuration.

    Update this list only when a human has recorded a framework decision in the lane
    README — never to make a scaffold pass.
    """
    contents = sorted(path.name for path in (repo_root / "webapp").iterdir())
    assert contents == ["AGENTS.md", "README.md"], (
        f"webapp/ should hold only its placeholder documents until a framework decision "
        f"is recorded, but it contains {contents}"
    )
