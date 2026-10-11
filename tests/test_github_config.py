"""GitHub configuration (REQ-040 to REQ-046)."""

from pathlib import Path

import pytest
import yaml

REQUIRED_GITHUB_FILES = (
    ".github/workflows/ci.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/task.md",
)
EXPECTED_JOBS = {"changes", "lint", "test", "notebooks", "firmware", "secrets", "ci-success"}


@pytest.mark.parametrize("name", REQUIRED_GITHUB_FILES)
def test_required_github_file_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing GitHub config: {name}"


def test_ci_workflow_is_valid_yaml_with_expected_jobs(repo_root: Path) -> None:
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    assert set(workflow["jobs"]) == EXPECTED_JOBS


def test_ci_has_aggregate_gate(repo_root: Path) -> None:
    """A required check whose job is skipped never reports, which would deadlock PRs."""
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    assert "ci-success" in workflow["jobs"]


def test_codeowners_covers_every_lane(repo_root: Path) -> None:
    content = (repo_root / ".github/CODEOWNERS").read_text(encoding="utf-8")
    for lane in ("firmware/", "notebooks/", "webapp/", "data/", "docs/", "specs/", "tests/"):
        assert lane in content, f"CODEOWNERS does not cover {lane}"
    assert "@andrewhmir" in content


def test_pull_request_template_requires_verification_and_lane(repo_root: Path) -> None:
    content = (repo_root / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8").lower()
    for required in ("what", "why", "verif", "lane"):
        assert required in content, f"PR template is missing a {required!r} section"


def test_gitattributes_forces_lf_for_lockfile_and_python(repo_root: Path) -> None:
    """Review Focus: CRLF in a lockfile or script breaks on another platform."""
    content = (repo_root / ".gitattributes").read_text(encoding="utf-8")
    assert "uv.lock" in content and "eol=lf" in content
    assert "*.sh" in content


def test_ci_does_not_run_lanes_that_do_not_exist(repo_root: Path) -> None:
    """A job must be guarded, or an unimplemented lane fails every pull request."""
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    for job_name in ("lint", "test", "notebooks", "firmware"):
        job = workflow["jobs"][job_name]
        assert "if" in job, f"job {job_name} is not guarded by a changed-path condition"
