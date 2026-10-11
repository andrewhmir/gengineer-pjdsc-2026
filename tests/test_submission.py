"""The deck and video are scored deliverables with hard numeric limits (REQ-060)."""

from pathlib import Path


def test_submission_readme_exists(repo_root: Path) -> None:
    assert (repo_root / "submission/README.md").is_file()


def test_submission_records_slide_and_video_limits(repo_root: Path) -> None:
    """Exceeding either limit costs points, so the limits are recorded where work happens."""
    content = (repo_root / "submission/README.md").read_text(encoding="utf-8")
    assert "20" in content and "slide" in content.lower()
    assert "3" in content and ("minute" in content.lower() or "min" in content.lower())


def test_submission_lists_every_required_deliverable(repo_root: Path) -> None:
    content = (repo_root / "submission/README.md").read_text(encoding="utf-8").lower()
    for deliverable in ("slide deck", "video", "repository"):
        assert deliverable.split()[0] in content, f"submission README omits the {deliverable}"
    assert "docs/sources.md" in content.lower()


def test_submission_links_the_repository(repo_root: Path) -> None:
    content = (repo_root / "submission/README.md").read_text(encoding="utf-8")
    assert "github.com/andrewhmir/gengineer-pjdsc-2026" in content


def test_no_large_binary_is_committed_in_submission(repo_root: Path) -> None:
    """REQ-031: the video is linked, not committed."""
    offenders = [
        path.name
        for path in (repo_root / "submission").rglob("*")
        if path.is_file() and path.stat().st_size > 1024 * 1024
    ]
    assert not offenders, f"committed files over 1 MB: {offenders}"
