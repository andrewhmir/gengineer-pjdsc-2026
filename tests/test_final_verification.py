"""Whole-repository acceptance checks that no single lane test owns.

These are the plan's final verification. Every assertion here has been shown to fail when
the fault it names is injected; the lane-map check below replaces the plan's version,
which skipped a lane whose row had been deleted (see its docstring).
"""

import json
import re
import subprocess
from pathlib import Path

MAX_COMMITTED_BYTES = 1024 * 1024

# The lane directories the repository's own documentation advertises, and the exact set
# the README's Repository map must carry one row for. Kept explicit rather than globbed:
# a glob over the repository root would sweep up `.venv/` and `.pytest_cache/`, and a
# lane is a documented concept, not any directory that happens to sit at the root. The
# single definition also stops the directory check and the lane-map check disagreeing
# about which lanes exist.
LANES = ("firmware", "data", "notebooks", "webapp", "submission", "tests", "docs", "specs")

# The tests lane's marquee rules. Named so a missing rule is a readable failure.
MARQUEE_TESTS_RULES = (
    "no hardware and no network",
    "never touch the real dataset",
    "mock the board",
)


def tracked_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line]


def readme_lane_map(repo_root: Path) -> dict[str, list[tuple[str, str]]]:
    """Return {lane: [(state, raw_row), ...]} for the README's Repository map table.

    Parses the table's *structure* — a first cell naming the lane directory and a third
    cell naming its state — instead of regex-searching for the lane name anywhere in the
    file. A substring search is the wrong tool here: it has no notion of which cell the
    match landed in.

    The value is a list, not a single tuple, because a duplicate row must be *visible* to
    the caller. Collapsing duplicates into a dict silently lets a second row for the same
    lane rewrite the first, so a lane could be documented twice with contradictory states
    and the row-set comparison would still pass.

    A row is identified by its first cell naming a lane directory, and its state is the
    third cell. There is deliberately **no minimum cell count that drops the row**: an
    earlier version required four cells, which silently discarded a three-cell row for a
    lane rather than failing, so a malformed row was invisible. A lane row too short to
    carry a state is now returned with the sentinel `<no state cell>`, which fails the
    legend check loudly instead of being dropped. The lane pattern in the first cell is
    distinctive enough on its own to keep the other tables in `README.md` (commands,
    competition facts) out.
    """
    rows: dict[str, list[tuple[str, str]]] = {}
    table = (repo_root / "README.md").read_text(encoding="utf-8")
    for line in table.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        match = re.search(r"`([a-z_]+)/`", cells[0])
        if match is None:
            continue
        state = cells[2] if len(cells) >= 3 else "<no state cell>"
        rows.setdefault(match.group(1), []).append((state, line))
    return rows


def agents_md_lane_map(repo_root: Path) -> set[str]:
    """Lane directories named in the root AGENTS.md lane map's first column."""
    lanes: set[str] = set()
    for line in (repo_root / "AGENTS.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0] in {"Folder", "---"}:
            continue
        lanes.update(re.findall(r"`([a-z_]+)/`", cells[0]))
    return lanes


def test_no_tracked_file_exceeds_one_megabyte(repo_root: Path) -> None:
    """REQ-031."""
    offenders = []
    for name in tracked_files(repo_root):
        path = repo_root / name
        if path.is_file() and path.stat().st_size > MAX_COMMITTED_BYTES:
            offenders.append((name, path.stat().st_size))
    assert not offenders, f"tracked files over 1 MB: {offenders}"


def test_repository_root_files_are_present(repo_root: Path) -> None:
    """REQ-012: the inventory the spec commits to."""
    required = (
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "LICENSE",
        "CITATION.cff",
        "AGENTS.md",
        "CLAUDE.md",
        "pyproject.toml",
        "uv.lock",
    )
    missing = [name for name in required if not (repo_root / name).is_file()]
    assert not missing, f"missing root files: {missing}"


def test_no_empty_placeholder_files_are_tracked(repo_root: Path) -> None:
    """REQ-013."""
    placeholders = [name for name in tracked_files(repo_root) if Path(name).name == ".gitkeep"]
    assert not placeholders, f"placeholder files found: {placeholders}"


def test_ci_status_check_name_matches_the_ruleset(repo_root: Path) -> None:
    """The required status check must match a job that actually exists."""
    import yaml

    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    setup = (repo_root / "docs/SETUP.md").read_text(encoding="utf-8")
    assert "ci-success" in workflow["jobs"]
    assert "ci-success" in setup, "SETUP.md must name the required status check"


def test_every_lane_exists(repo_root: Path) -> None:
    """Whole-repository check: by the end of the plan every advertised lane is real.

    Task 8 deliberately asserts only the README text, because four of these lanes do not
    exist until Tasks 4-7.
    """
    for lane in LANES:
        assert (repo_root / lane).is_dir(), f"lane {lane}/ is documented but absent"


def test_lane_readmes_are_present_where_they_are_expected(repo_root: Path) -> None:
    """A lane directory with no README is unreviewable and unannounced.

    `tests/`, `docs/` and `specs/` are cross-cutting rather than lanes and carry different
    entry points, so the README requirement is scoped to the five lanes whose README is
    the door into the lane.
    """
    for lane in ("firmware", "data", "notebooks", "webapp", "submission"):
        assert (repo_root / lane / "README.md").is_file(), f"{lane}/ has no README.md"


def test_tests_agents_md_states_the_marquee_rules(repo_root: Path) -> None:
    """`tests/AGENTS.md` is the lane file every test author reads first.

    Each rule is asserted as its own phrase. An ``any(...)`` check over the list would
    stay green when two of the three rules were deleted, which is the defect this shape
    exists to prevent.
    """
    content = (repo_root / "tests/AGENTS.md").read_text(encoding="utf-8").lower()
    for rule in MARQUEE_TESTS_RULES:
        assert rule in content, f"tests/AGENTS.md no longer states the rule: {rule!r}"


def test_suite_pins_ruff_to_the_pre_commit_rev(repo_root: Path) -> None:
    """The two cases that must agree, or `ruff format --check` differs locally and in CI.

    Both patterns are anchored to the exact line shape they are looking for, and each is
    required to match exactly once.

    The pyproject pattern is anchored to a dependency line at the dev group's four-space
    indent. An unanchored search takes the *first* occurrence of the pin anywhere in the
    file, so prose or a comment that merely mentions the expected version above a
    genuinely drifted pin satisfies the assertion while the invariant is broken. That is
    not hypothetical: an earlier revision of this docstring quoted the expected version on
    its own line and made the test fail against itself, which is how the weakness surfaced.

    The rev pattern anchors to the `ruff-pre-commit` repository URL and treats the
    explanatory comment between it and `rev:` as optional. Requiring that comment made
    deleting it, a semantically neutral edit, turn the test red with a misleading
    "could not locate" message. Both halves of this fix were verified by constructing the
    decoy comment and the comment-deletion edit and confirming the outcome in each case.
    """
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    precommit = (repo_root / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    pins = re.findall(r'^    "ruff==([0-9.]+)",\s*$', pyproject, re.MULTILINE)
    assert len(pins) == 1, f"expected exactly one ruff pin line in pyproject.toml, got {pins}"

    revs = re.findall(r"ruff-pre-commit\s*\n(?:\s*#.*\n)?\s*rev:\s*v?([0-9.]+)", precommit)
    assert len(revs) == 1, f"expected exactly one ruff-pre-commit rev, got {revs}"

    assert pins[0] == revs[0], f"ruff is pinned to {pins[0]} but the pre-commit rev is v{revs[0]}"


def test_lane_map_agrees_with_the_filesystem(repo_root: Path) -> None:
    """The lane map must name every documented lane, and the two lane maps must agree.

    The plan prescribed this body:

        row = re.search(rf"^\\|.*`?{lane}/`?.*$", readme, re.MULTILINE)
        if not row:
            continue
        landed = (repo_root / lane / "README.md").is_file()
        says_planned = "planned" in row.group(0).lower()
        assert landed != says_planned

    Measured on this tree, that assertion is **green, not vacuous** — it has two live
    branches (`landed=False, says_planned=False` and `landed=True, says_planned=True`
    both go red). Its real defect is the ``if not row: continue``: a lane whose row is
    deleted from the map is skipped entirely, so dropping `submission/` from the table
    would leave the check green and silent. It also cannot see a duplicate row.

    Two claims made about the original during this task were **wrong and are retracted**:
    it is not "100% vacuous", and its greedy row regex does **not** cross-match the
    `notebooks` row — `README.md:48`'s Lane cell is "Data / analysis" with a space, which
    does not contain the substring "data/", so each of the five patterns matches exactly
    its own row. Both claims were reasoned about rather than executed; re-run against the
    file, `data/` matches line 47 only.

    What this version adds over the plan's body, each falsified by injection:

    * the map carries exactly one row per documented lane, names no undocumented lane, and
      documents no lane twice (the ``continue`` hole and the duplicate hole, both closed);
    * every state word the map uses is one the legend defines;
    * every lane the root `AGENTS.md` names exists on disk and appears in the README map,
      so a lane added to one document cannot go missing from the other.

    The third point is a **subset** relation, not an equality: `AGENTS.md`'s lane map
    covers 5 of the 8 README lanes, so it is asserted as "everything the AGENTS map names
    is also in the README map", not "the two sets are equal".

    Lane *existence* is deliberately not re-asserted in the row loop: this function
    already requires `set(rows) == set(LANES)`, so a lane absent from disk would have to
    be absent from the map too, which the row-set comparison catches first.
    """
    rows = readme_lane_map(repo_root)
    assert set(rows) == set(LANES), (
        "the README Repository map must carry exactly one row per documented lane; "
        f"missing={sorted(set(LANES) - set(rows))} "
        f"unexpected={sorted(set(rows) - set(LANES))}"
    )
    duplicated = {lane: len(entries) for lane, entries in rows.items() if len(entries) > 1}
    assert not duplicated, (
        f"the README Repository map documents a lane more than once: {duplicated}; "
        "a duplicate row silently overrides the first and hides a contradiction"
    )

    # README -> disk: a documented lane must be real, and must declare a state the
    # legend defines rather than a word the table has invented.
    legend = (repo_root / "README.md").read_text(encoding="utf-8")
    vocabulary = {
        word
        for line in legend.splitlines()
        if line.startswith("- **")
        for word in re.findall(r"\*\*([a-z]+)\*\*", line)
    }
    for lane, entries in rows.items():
        for state, row in entries:
            assert state in vocabulary, (
                f"{lane}/ is mapped to state {state!r}, which the legend does not define "
                f"(legend: {sorted(vocabulary)}); row: {row}"
            )

    # AGENTS.md <-> README: the root lane map and the human lane map must agree.
    agents_lanes = agents_md_lane_map(repo_root)
    assert agents_lanes, "the root AGENTS.md has no lane map, so this check is vacuous"
    for lane in sorted(agents_lanes):
        assert (repo_root / lane).is_dir(), f"AGENTS.md names {lane}/, which does not exist"
    undocumented = agents_lanes - set(rows)
    assert not undocumented, (
        f"AGENTS.md documents lanes the README Repository map omits: {sorted(undocumented)}"
    )


def declared_notebook_reads(notebook: Path) -> list[str]:
    """Literal `read_csv("...")` targets declared by one notebook's code cells.

    Only string literals are found. A computed path such as
    `pd.read_csv(Path("../data/samples/x.csv"))` is invisible here, which is why the
    companion guard below requires *some* notebook to declare a literal read rather than
    asserting every notebook does.
    """
    document = json.loads(notebook.read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell["source"]) for cell in document["cells"] if cell["cell_type"] == "code"
    )
    return re.findall(r'read_csv\(\s*["\']([^"\']+)["\']', source)


def test_notebook_relative_paths_resolve_on_disk(repo_root: Path) -> None:
    """Close the class of defect that was invisible to the unit suite.

    Both Task 6 defects — the undeclared pandas import and the repository-root fixture
    path — passed `uv run pytest` and were caught only by `--nbmake`, because the static
    notebook tests inspect JSON and never resolve a path. This test resolves each
    notebook's declared data paths against the notebook's OWN directory first, matching
    nbmake's working directory (`nb_run.py`: `c.execute(cwd=self.filename.parent)`), so a
    future notebook with an unresolvable path fails locally rather than only in CI.
    """
    notebooks = sorted((repo_root / "notebooks").glob("*.ipynb"))
    assert notebooks, "no notebooks were found, so this check is vacuous"
    for notebook in notebooks:
        for relative in declared_notebook_reads(notebook):
            resolved = (notebook.parent / relative).resolve()
            assert resolved.is_file(), (
                f"{notebook.name} reads {relative!r}, which resolves to {resolved} "
                "relative to the notebook and does not exist"
            )


def test_the_notebook_fixture_path_is_actually_exercised(repo_root: Path) -> None:
    """Guard the guard: the resolver above must find at least one declared read.

    Without this, a refactor that stopped using `read_csv` (or renamed the fixture) would
    make `test_notebook_relative_paths_resolve_on_disk` iterate zero paths and pass while
    checking nothing — the same shape of vacuity this module exists to eliminate.

    Counted over the whole lane, and the count is asserted per notebook that declares
    anything. A pooled `list.extend` across notebooks would let one notebook's declaration
    satisfy the guard while a second notebook contributed zero paths to the resolver —
    measured, and the reason this reports per-notebook counts rather than one total.
    """
    counts = {
        notebook.name: len(declared_notebook_reads(notebook))
        for notebook in sorted((repo_root / "notebooks").glob("*.ipynb"))
    }
    assert any(counts.values()), (
        "no notebook declares a read_csv path, so the notebook path resolver checks "
        "nothing; update this test if the notebook lane changes how it loads fixtures"
    )
    silent = sorted(name for name, count in counts.items() if count == 0)
    assert not silent, (
        f"these notebooks declare no literal read_csv path and so contribute nothing to "
        f"the resolver: {silent} (declared per notebook: {counts})"
    )
