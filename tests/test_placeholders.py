"""The webapp lane is no longer a placeholder: it owns a recorded decision.

An earlier version of this file asserted that the lane held exactly two files and that no
framework had been chosen. That was true until 2026-10-17, when the maintainer chose FastAPI
and the lane gained its own manifest. The assertions now pin the *decision* and its evidence,
so the lane cannot silently slide back to a placeholder or lose its lockfile.
"""

from pathlib import Path


def test_webapp_readme_records_the_framework_decision(repo_root: Path) -> None:
    """The decision is dated and named, not implied by the presence of code."""
    content = (repo_root / "webapp/README.md").read_text(encoding="utf-8").lower()
    assert "fastapi" in content and "jinja2" in content
    assert "2026-10-17" in content


def test_webapp_owns_its_manifest_and_lockfile(repo_root: Path) -> None:
    """REQ-118: the lane resolves its own environment; the root project excludes it."""
    assert (repo_root / "webapp/pyproject.toml").is_file()
    assert (repo_root / "webapp/uv.lock").is_file()
    root = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "tool.uv.workspace" in root


def test_webapp_suite_is_present(repo_root: Path) -> None:
    """A lane with code but no tests would be a lane that cannot be verified."""
    tests = repo_root / "webapp/tests"
    assert tests.is_dir()
    assert any(path.name.startswith("test_") for path in tests.iterdir())
