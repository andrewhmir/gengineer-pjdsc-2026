"""The frame contract and the buffers the detector reads.

A frame is the only thing the source layer and the pipeline agree on, so the parser has to be
strict about the fields the detector depends on and forgiving about anything a future firmware
adds. The buffers are time-indexed, not index-indexed: every window the station asks for is a
time range, so a test can preload a whole session and move a fake clock through it.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from hinigram.contracts import Frame
from hinigram.pipeline.frames import FrameStore, parse_frame_line


def test_frame_roundtrips_through_the_parser() -> None:
    line = (
        '{"v": 1, "t": 1792243200123, "tx": "tx2", "ch": 6, "seq": 42, '
        '"rssi": -42.5, "amp": [12, 14, 9], "phase": [-31, 5, 77]}'
    )
    frame = parse_frame_line(line)
    assert frame is not None
    assert frame.tx == "tx2"
    assert frame.t == 1792243200123
    assert frame.phase == [-31, 5, 77]


@pytest.mark.parametrize(
    "line",
    [
        '{"t": 1, "tx": "tx1"}',  # no version, no channels
        "not json",
        "",
        '{"v": 9, "t": 1, "tx": "tx1", "ch": 3, "seq": 0, "rssi": -40, "amp": [1], "phase": [0]}',
        b'{"v": 1, "t": 1, "tx": "tx4", "ch": 3, "seq": 0, "rssi": -40, "amp": [1], "phase": [0]}',
        # A frame with no version at all: the design counts it malformed, and the version field
        # is the mitigation for a firmware that changes the payload shape.
        (
            '{"t": 1, "tx": "tx1", "ch": 3, "seq": 0, "rssi": -40, '
            '"amp": [1, 2, 3], "phase": [0, 0, 0]}'
        ),
        # amp and phase describe the same subcarriers; a mismatch would break the buffer write.
        (
            '{"v": 1, "t": 1, "tx": "tx1", "ch": 3, "seq": 0, "rssi": -40, '
            '"amp": [1, 2, 3, 4], "phase": [0, 1]}'
        ),
    ],
)
def test_malformed_lines_are_rejected(line: str | bytes) -> None:
    assert parse_frame_line(line) is None


def test_a_frame_with_mismatched_subcarriers_cannot_be_built() -> None:
    with pytest.raises(ValidationError):
        Frame(v=1, t=1, tx="tx1", ch=3, seq=0, rssi=-40.0, amp=[1, 2, 3, 4], phase=[0, 1])


def test_window_returns_only_frames_inside_the_range(
    make_frame: Callable[..., Frame],
) -> None:
    store = FrameStore()
    for i in range(100):
        store.push(make_frame(t=1000 + i * 10))
    window = store.window(1100, 1400)
    assert window["tx1"].t.min() >= 1100
    assert window["tx1"].t.max() <= 1400
    assert window["tx1"].phase.shape[1] == 3


def test_the_window_reports_its_sample_rate(make_frame: Callable[..., Frame]) -> None:
    store = FrameStore()
    for i in range(200):
        store.push(make_frame(t=i * 10))
    assert store.window(0, 2000)["tx1"].fs == pytest.approx(100.0, rel=0.01)


def test_a_window_with_too_few_samples_has_no_usable_rate(
    make_frame: Callable[..., Frame],
) -> None:
    store = FrameStore()
    store.push(make_frame(t=0))
    window = store.window(0, 10)["tx1"]
    assert window.fs == pytest.approx(100.0)  # documented fallback, not a division by zero


def test_ring_buffer_drops_the_oldest_frames(make_frame: Callable[..., Frame]) -> None:
    store = FrameStore(capacity=10)
    for i in range(25):
        store.push(make_frame(t=i * 10))
    assert store.counters().per_tx["tx1"] == 25
    assert store.window(0, 1000)["tx1"].t.shape[0] == 10


def test_counters_separate_accepted_and_malformed_frames(
    make_frame: Callable[..., Frame],
) -> None:
    store = FrameStore()
    store.push(make_frame(t=10, tx="tx1"))
    store.push(make_frame(t=20, tx="tx2"))
    store.count_malformed()
    counters = store.counters()
    assert counters.frames == 2
    assert counters.malformed == 1
    assert counters.per_tx == {"tx1": 1, "tx2": 1}
    assert counters.last_t == 20


def test_reset_clears_every_channel(make_frame: Callable[..., Frame]) -> None:
    store = FrameStore()
    store.push(make_frame(t=10))
    store.reset()
    assert store.window(0, 1000) == {}
    assert store.counters().frames == 0
    assert store.counters().last_t is None


def test_an_empty_window_is_absent_rather_than_empty(
    make_frame: Callable[..., Frame],
) -> None:
    """Callers must not have to distinguish 'no frames' from 'a zero-length array'."""
    store = FrameStore()
    store.push(make_frame(t=10))
    assert store.window(5000, 6000) == {}
