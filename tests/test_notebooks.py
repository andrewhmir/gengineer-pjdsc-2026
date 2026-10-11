"""Notebook hygiene: outputs in git leak data and bloat the clone."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE = "../data/samples/public_health_indicators.csv"


def notebook_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "notebooks").glob("*.ipynb"))


def nbmake_collects(repo_root: Path, target: Path) -> bool:
    """Collect `target` with nbmake in a child process; return True if it is collected.

    The judgement is nbmake's own, taken from the child pytest's exit code — this helper
    must never second-guess the path itself, or the assertions below would restate this
    file's opinion rather than test nbmake's behaviour.

    The interpreter is `sys.executable` rather than `uv run`: `uv` need not be on PATH, and
    `uv run` inside an already-running test fails here with a cache `Access is denied` error.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--nbmake", str(target), "--collect-only", "-q"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode == pytest.ExitCode.OK


def test_notebook_lane_has_a_template(repo_root: Path) -> None:
    assert (repo_root / "notebooks/_template.ipynb").is_file()


def test_every_notebook_has_no_outputs(repo_root: Path) -> None:
    """Pinned Review Focus item: committed outputs leak data and bloat the repo.

    Iterates the whole lane, not just the template. nbmake does not fail a notebook that
    carries stored outputs, and the nbstripout pre-commit hook cannot run on the
    maintainer's machine, so a committed output in a future numbered notebook would
    otherwise be caught by nothing.
    """
    for path in notebook_paths(repo_root):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            assert not cell.get("outputs"), f"{path.name} cell {index} contains stored output"
            assert cell.get("execution_count") is None, (
                f"{path.name} cell {index} has an execution count"
            )


def test_notebook_selection_is_path_based_not_tag_based(repo_root: Path, tmp_path: Path) -> None:
    """Guard the collection mechanism, replacing a test that pinned an inert field.

    An earlier version asserted that a top-level ``metadata.tags`` entry named ``nbmake``
    selected the notebook for CI. It does not: nbmake's collection predicate is
    ``nbmake_enabled and p.match("*ipynb") and "_build" not in p.parts``, and it reads no
    notebook metadata at all. Location is the only opt-in, so a notebook cannot opt out by
    dropping a tag, and a scratch notebook left in the lane *will* be executed by CI.

    The same file is placed in two locations and the outcome is decided by nbmake in a child
    process each time, so the assertion is behaviour rather than a restatement of the rule.
    Weakening nbmake's predicate to drop the ``_build`` exclusion makes the first assertion
    fail, which is how this test was verified as non-vacuous.
    """
    tagged = tmp_path / "tag_probe.ipynb"
    shutil.copy(repo_root / "notebooks/_template.ipynb", tagged)

    # A valid notebook, excluded only by where it sits.
    excluded = tmp_path / "_build" / "excluded_probe.ipynb"
    excluded.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(tagged, excluded)
    assert not nbmake_collects(repo_root, excluded), (
        "a notebook under a _build directory was collected, so nbmake's exclusion rule "
        "changed and this test must be revisited"
    )

    # The identical file, included purely because of where it lives.
    assert nbmake_collects(repo_root, tagged), (
        "a notebook outside an excluded path was not collected"
    )

    # And the lane's own notebooks are collected, since location is the whole opt-in.
    assert nbmake_collects(repo_root, repo_root / "notebooks")


def test_no_notebook_uses_an_absolute_path(repo_root: Path) -> None:
    """Absolute paths break for every other clone and for the judges.

    Iterates the lane so a future notebook cannot slip an absolute path past a check that
    only ever looked at the template. The path itself is resolved by the whole-repository
    test in the final verification task.
    """
    for path in notebook_paths(repo_root):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        source = "\n".join(
            "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
        )
        assert "C:\\" not in source and "/Users/" not in source, (
            f"{path.name} contains an absolute path"
        )


def test_template_reads_the_sample_by_notebook_relative_path(repo_root: Path) -> None:
    """The template must keep reading the fixture the way nbmake can actually resolve it.

    The path is asserted notebook-relative, because nbmake executes a notebook with the
    notebook's own directory as the working directory. A repository-root path such as
    `data/samples/...` resolves to `notebooks/data/samples/...` and does not exist.
    """
    notebook = json.loads((repo_root / "notebooks/_template.ipynb").read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    assert FIXTURE in source
