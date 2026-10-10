"""Notebook hygiene: outputs in git leak data and bloat the clone."""

import json
from pathlib import Path


def notebook_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "notebooks").glob("*.ipynb"))


def test_notebook_lane_has_a_template(repo_root: Path) -> None:
    assert (repo_root / "notebooks/_template.ipynb").is_file()


def test_template_notebook_has_no_outputs(repo_root: Path) -> None:
    """Pinned Review Focus item: committed outputs leak data and bloat the repo."""
    notebook = json.loads((repo_root / "notebooks/_template.ipynb").read_text(encoding="utf-8"))
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        assert not cell.get("outputs"), f"cell {index} contains stored output"
        assert cell.get("execution_count") is None, f"cell {index} has an execution count"


def test_template_notebook_is_marked_for_nbmake(repo_root: Path) -> None:
    notebook = json.loads((repo_root / "notebooks/_template.ipynb").read_text(encoding="utf-8"))
    assert "nbmake" in notebook.get("metadata", {}).get("tags", [])


def test_template_notebook_uses_relative_sample_path(repo_root: Path) -> None:
    """Absolute paths break for every other clone and for the judges.

    The path is asserted **notebook-relative**, because `nbmake` executes a
    notebook with the notebook's own directory as the working directory. A
    repository-root path such as `data/samples/...` resolves to
    `notebooks/data/samples/...` and does not exist.
    """
    notebook = json.loads((repo_root / "notebooks/_template.ipynb").read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    assert "../data/samples/public_health_indicators.csv" in source
    assert "C:\\" not in source and "/Users/" not in source
