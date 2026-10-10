"""Firmware lane invariants.

CI cannot prove firmware runs on hardware. What it can prove is that the code
byte-compiles, avoids host-only constructs, and does not reach out of its own
lane — the three ways a CircuitPython program fails at boot.
"""

import ast
import py_compile
from pathlib import Path

import pytest

FIRMWARE_FORBIDDEN_CALLS = {"dataclass"}  # dataclasses are unavailable on CircuitPython
FIRMWARE_FORBIDDEN_NODES = (ast.Match,)  # match statements are unavailable
HOST_ONLY_ROOT_MODULES = {"tests", "notebooks", "webapp", "docs", "specs", "data"}


def firmware_sources(repo_root: Path) -> list[Path]:
    return sorted(
        path for path in (repo_root / "firmware").rglob("*.py") if "lib" not in path.parts
    )


def test_firmware_lane_has_sources(repo_root: Path) -> None:
    assert firmware_sources(repo_root), "firmware lane must contain at least code.py"


def test_firmware_sources_compile(repo_root: Path) -> None:
    for source in firmware_sources(repo_root):
        try:
            py_compile.compile(str(source), doraise=True, cfile=None)
        except py_compile.PyCompileError as exc:  # pragma: no cover - failure path
            pytest.fail(f"{source} does not byte-compile: {exc}")


def test_code_py_has_no_forbidden_constructs(repo_root: Path) -> None:
    """CircuitPython lacks dataclasses and match statements."""
    tree = ast.parse((repo_root / "firmware/code.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        assert not isinstance(node, FIRMWARE_FORBIDDEN_NODES), (
            "match is unavailable on CircuitPython"
        )
        if isinstance(node, ast.ImportFrom) and node.module in FIRMWARE_FORBIDDEN_CALLS:
            pytest.fail("dataclasses is unavailable on CircuitPython")


def test_firmware_does_not_import_repo_root(repo_root: Path) -> None:
    """firmware/ is copied to a CIRCUITPY drive; the repository does not travel with it."""
    for source in firmware_sources(repo_root):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = {node.module.split(".")[0]}
            else:
                continue
            offenders = roots & HOST_ONLY_ROOT_MODULES
            assert not offenders, f"{source} imports host-only modules: {sorted(offenders)}"


def test_code_py_imports_cleanly_off_device(repo_root: Path) -> None:
    """The hardware import is guarded, so the module is importable on a laptop."""
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("firmware_code", repo_root / "firmware" / "code.py")
    assert spec is not None and spec.loader is not None
    firmware_code = module_from_spec(spec)
    spec.loader.exec_module(firmware_code)
    assert firmware_code.HARDWARE_AVAILABLE is False
    assert isinstance(firmware_code.run_check(), str)


def test_secrets_template_exists_and_real_file_is_ignored(repo_root: Path) -> None:
    assert (repo_root / "firmware/secrets.example.py").is_file()
