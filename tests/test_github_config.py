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
EXPECTED_JOBS = {
    "changes",
    "lint",
    "test",
    "notebooks",
    "firmware",
    "webapp",
    "secrets",
    "ci-success",
}


@pytest.mark.parametrize("name", REQUIRED_GITHUB_FILES)
def test_required_github_file_exists(repo_root: Path, name: str) -> None:
    assert (repo_root / name).is_file(), f"missing GitHub config: {name}"


def test_ci_workflow_is_valid_yaml_with_expected_jobs(repo_root: Path) -> None:
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    assert set(workflow["jobs"]) == EXPECTED_JOBS


def test_ci_has_aggregate_gate(repo_root: Path) -> None:
    """A required check whose job is skipped never reports, which would deadlock PRs.

    The gate is asserted **semantically**, not merely as a key that exists. An earlier
    version checked only `"ci-success" in workflow["jobs"]`, which left every one of these
    regressions green: dropping `if: always()`, dropping a job from `needs`, pointing the
    gate at the wrong job set, or inverting the polarity. YAML parsing validates structure,
    not meaning, and Task 11 makes this exact job name a required status check.
    """
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    gate = workflow["jobs"]["ci-success"]

    assert gate["if"] == "always()", (
        "the aggregate gate must run even when upstream jobs are skipped, or a skipped "
        "required check never reports and pull requests can never merge"
    )
    assert set(gate["needs"]) == EXPECTED_JOBS - {"ci-success"}, (
        "the gate must depend on every other job, or a failing lane could report green"
    )
    script = " ".join(str(step.get("run", "")) for step in gate["steps"])
    assert "failure" in script and "cancelled" in script, (
        "the gate must fail on a failed or cancelled job; it may only treat `skipped` "
        "and `success` as passing"
    )
    assert "jq" in script and "command -v jq" in script, (
        "the gate must verify jq exists, or a missing jq exits 127 and the gate reports "
        "success even when a required job failed"
    )


def test_ci_workflow_triggers_on_push_and_pull_request(repo_root: Path) -> None:
    """Deleting the triggers would make every check vacuous without failing anything."""
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    # `on` parses as the boolean True key in YAML 1.1, so accept either spelling.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers is not None, "the workflow has no `on:` triggers at all"
    assert "pull_request" in triggers and "push" in triggers


def test_ci_push_diff_covers_the_whole_push(repo_root: Path) -> None:
    """A push must diff every commit it delivered, not just the last one.

    Regression guard for a bug that shipped green. The script used ``HEAD~1`` on the
    push path, so a three-commit push was diffed down to its final commit only. The
    changed-path outputs then saw a single test file, ``lint`` and ``test`` were
    skipped, and because the aggregate gate treats skipped as passed, ``ci-success``
    reported success while the suite never ran. Observed on the very first real run
    (run 38146155506: the `Tests` job concluded `skipped`).
    """
    content = (repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "github.event.before" in content, (
        "the push path must diff from `github.event.before`, or a multi-commit push is "
        "only partially checked"
    )
    assert 'base="HEAD~1"' not in content, (
        "diffing `HEAD~1` on push inspects only the last commit of the push, letting "
        "`ci-success` report green while the suite is skipped"
    )


def test_ci_handles_a_base_that_no_longer_exists(repo_root: Path) -> None:
    """A force-push leaves `github.event.before` naming an unreachable commit.

    Regression guard for a failure observed on this repository's own force-push:
    `git diff 8c4ea5b...2e1e79b` died with "fatal: Invalid symmetric difference
    expression" (exit 128), the `changes` job failed, and the aggregate gate failed with
    it. Any rebase, amend, or squash-merge of a pushed branch can do this, so the script
    must verify the base exists in the clone and fall back to one that does.
    """
    content = (repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "git cat-file -e" in content, (
        "the script must verify the chosen base exists, or a rewritten history breaks CI"
    )
    assert "git merge-base HEAD origin/main" in content, (
        "a missing base must fall back to a commit that exists, not be used blindly"
    )


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
    """A job must be guarded on ITS OWN changed-path output.

    Asserting only that an `if` key exists leaves three regressions green: pointing a guard
    at the wrong output (running `test` off the `notebooks` signal), inverting it
    (`== 'false'`), or swapping two jobs' guards. Each guard is therefore pinned to its own
    output name.
    """
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    own_output = {
        "lint": "python",
        "test": "python",
        "notebooks": "notebooks",
        "firmware": "firmware",
        "webapp": "webapp",
    }
    for job_name, output in own_output.items():
        guard = workflow["jobs"][job_name]["if"]
        assert f"changes.outputs.{output}" in guard, (
            f"job {job_name} is not guarded on its own `{output}` output: {guard!r}"
        )
        assert "== 'true'" in guard, (
            f"job {job_name}'s guard does not require true, so it may run (or skip) "
            f"inverted: {guard!r}"
        )
