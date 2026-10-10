"""Documentation completeness and rubric-driven artifacts (REQ-014, REQ-063)."""

from pathlib import Path

import pytest

REQUIRED_DOCS = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "LICENSE",
    "CITATION.cff",
    ".env.example",
    "docs/README.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA.md",
    "docs/SOURCES.md",
    "docs/SETUP.md",
)


@pytest.mark.parametrize("name", REQUIRED_DOCS)
def test_required_document_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing required document: {name}"


def test_readme_contains_working_quickstart(repo_root: Path) -> None:
    """REQ-063: a stranger must be able to run the project from the README alone."""
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "uv sync" in readme, "README must document the one-command setup"
    assert "uv run pytest" in readme, "README must document how to run the tests"


def test_readme_states_the_competition_theme(repo_root: Path) -> None:
    readme = (repo_root / "README.md").read_text(encoding="utf-8").lower()
    assert "public health" in readme
    assert "pjdsc" in readme


def test_sources_documents_apa_seventh_edition(repo_root: Path) -> None:
    """REQ-014: 'Sources' is a scored rubric criterion."""
    sources = (repo_root / "docs/SOURCES.md").read_text(encoding="utf-8")
    assert "APA" in sources and "7th" in sources


def test_data_doc_prohibits_personal_health_data(repo_root: Path) -> None:
    """Privacy obligation under RA 10173."""
    data_doc = (repo_root / "docs/DATA.md").read_text(encoding="utf-8")
    assert "10173" in data_doc
    assert "real patient" in data_doc.lower() or "personally identifiable" in data_doc.lower()
