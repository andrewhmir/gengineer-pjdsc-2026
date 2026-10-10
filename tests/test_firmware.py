"""Firmware lane invariants.

CI cannot prove firmware runs on hardware. What it can prove is that the code
byte-compiles, avoids host-only constructs, and does not reach out of its own
lane — the three ways a CircuitPython program fails at boot.
"""

import ast
import py_compile
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest

# The module name, not the decorator name: `from dataclasses import dataclass` binds
# `dataclass`, but the node's `module` is `dataclasses`. Matching the decorator name
# misses both import forms and leaves a safety check that can never fail.
FIRMWARE_FORBIDDEN_MODULES = {"dataclasses"}  # the module does not exist on CircuitPython
FIRMWARE_FORBIDDEN_NODES = (ast.Match,)  # match statements are unavailable
HOST_ONLY_ROOT_MODULES = {"tests", "notebooks", "webapp", "docs", "specs", "data"}


def firmware_sources(repo_root: Path) -> list[Path]:
    """First-party firmware sources, excluding the vendored `lib/` directory."""
    return sorted(
        path for path in (repo_root / "firmware").rglob("*.py") if "lib" not in path.parts
    )


def imported_roots(tree: ast.AST) -> set[str]:
    """Root module names imported anywhere in `tree`, from both import forms."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def load_code_module(repo_root: Path) -> ModuleType:
    """Load `code.py` by path, under an isolated module name.

    `firmware/` must never go on `sys.path`: the filename `code.py` is required by
    CircuitPython and is also a CPython standard-library module name, so putting it
    on the path would shadow `code` for everything else in the session. Writing
    bytecode is disabled so the check leaves no `__pycache__/` behind in the lane.
    """
    spec = spec_from_file_location("firmware_code", repo_root / "firmware" / "code.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def test_firmware_lane_has_sources(repo_root: Path) -> None:
    assert firmware_sources(repo_root), "firmware lane must contain at least code.py"


def test_firmware_sources_compile(repo_root: Path) -> None:
    for source in firmware_sources(repo_root):
        try:
            py_compile.compile(str(source), doraise=True, cfile=None)
        except py_compile.PyCompileError as exc:  # pragma: no cover - failure path
            pytest.fail(f"{source} does not byte-compile: {exc}")


def test_firmware_sources_have_no_forbidden_constructs(repo_root: Path) -> None:
    """CircuitPython lacks dataclasses and match statements.

    Every first-party source is checked, not just `code.py`, because the lane rules
    allow a new module as a sibling of `code.py` — a check that only read `code.py`
    would let the next module evade it.
    """
    for source in firmware_sources(repo_root):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, FIRMWARE_FORBIDDEN_NODES):
                pytest.fail(f"{source} uses `match`, which is unavailable on CircuitPython")
        offenders = imported_roots(tree) & FIRMWARE_FORBIDDEN_MODULES
        if offenders:
            pytest.fail(
                f"{source} imports {sorted(offenders)}, which is unavailable on CircuitPython"
            )


def test_firmware_does_not_import_repo_root(repo_root: Path) -> None:
    """firmware/ is copied to a CIRCUITPY drive; the repository does not travel with it."""
    for source in firmware_sources(repo_root):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        offenders = imported_roots(tree) & HOST_ONLY_ROOT_MODULES
        assert not offenders, f"{source} imports host-only modules: {sorted(offenders)}"


def test_code_py_imports_cleanly_off_device(repo_root: Path) -> None:
    """The hardware import is guarded, so the module is importable on a laptop."""
    firmware_code = load_code_module(repo_root)
    assert firmware_code.HARDWARE_AVAILABLE is False
    status = firmware_code.run_check()
    assert isinstance(status, str)
    assert "no hardware" in status, f"off-device status must say so, got: {status!r}"


def test_code_py_status_when_hardware_is_present(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hardware-present branch is reachable: it is what the board will execute.

    Nothing on a laptop can import the real `board` or `busio`, so the seam is
    exercised by seeding stand-ins into `sys.modules` — the same injection a
    host-side fake uses, and the reason the import sits behind a guard.
    """
    saved = {name: sys.modules.get(name) for name in ("board", "busio")}
    monkeypatch.setitem(sys.modules, "board", ModuleType("board"))
    monkeypatch.setitem(sys.modules, "busio", ModuleType("busio"))
    try:
        firmware_code = load_code_module(repo_root)
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    assert firmware_code.HARDWARE_AVAILABLE is True
    status = firmware_code.run_check()
    assert isinstance(status, str)
    assert "hardware" in status, f"on-device status must mention hardware, got: {status!r}"
    assert "no hardware" not in status


def test_secrets_template_exists_and_real_file_is_ignored(repo_root: Path) -> None:
    assert (repo_root / "firmware/secrets.example.py").is_file()
    tracked = subprocess.run(
        ["git", "check-ignore", "-q", "firmware/secrets.py"],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    assert tracked.returncode == 0, (
        "firmware/secrets.py must be gitignored, or real credentials can be committed"
    )
