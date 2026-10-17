"""Shared fixtures for the lane suite.

Clocks and frame sources are always injected: the suite must be deterministic and finish in
seconds, so no test waits on wall-clock time or on a background thread for real frames.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hinigram.app import create_app
from hinigram.config import Settings
from hinigram.contracts import Frame


class FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self, start_ms: int = 1_000_000) -> None:
        self._now = start_ms

    def now(self) -> int:
        return self._now

    def advance(self, ms: int) -> int:
        self._now += ms
        return self._now


@pytest.fixture
def settings_factory(tmp_path: Path) -> Callable[..., Settings]:
    """Build a ``Settings`` whose file paths stay inside the test's temp directory."""

    def factory(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "source": "sim",
            "replay_file": tmp_path / "replay_session.jsonl.gz",
        }
        values.update(overrides)
        return Settings(**values)  # type: ignore[arg-type]

    return factory


@pytest.fixture
def client(settings_factory: Callable[..., Settings]) -> Iterator[TestClient]:
    """An HTTP client over the real app, with the lifespan entered."""
    with TestClient(create_app(settings_factory())) as test_client:
        yield test_client


@pytest.fixture
def make_frame() -> Callable[..., Frame]:
    """Build a valid CSI frame; tests override only the fields they care about."""

    def factory(
        t: int,
        tx: str = "tx1",
        phase: list[float] | None = None,
        amp: list[float] | None = None,
        ch: int = 3,
    ) -> Frame:
        return Frame(
            v=1,
            t=t,
            tx=tx,  # type: ignore[arg-type]
            ch=ch,
            seq=0,
            rssi=-42.0,
            amp=amp if amp is not None else [1.0] * ch,
            phase=phase if phase is not None else [0.0] * ch,
        )

    return factory
