"""The wire contracts themselves: what the payload must contain, and what it may never contain."""

from __future__ import annotations

from typing import get_args

import pytest
from fastapi.testclient import TestClient

from hinigram.contracts import Confidence, Outcome, Result, RuleName, SessionState, Trace
from tests.helpers import FakeClock


def test_the_outcome_vocabulary_is_exactly_three_words() -> None:
    assert get_args(Outcome) == ("regular", "irregular", "unclear")


def test_the_rule_vocabulary_is_closed() -> None:
    assert set(get_args(RuleName)) == {"none", "tachypnea", "apnea", "unsteady", "low_quality"}
    assert set(get_args(Confidence)) == {"high", "low", "none"}


def test_a_finished_session_validates_against_its_model(
    client: TestClient, clock: FakeClock
) -> None:
    client.post("/api/v1/session")
    clock.advance(33_500)
    payload = client.get("/api/v1/session").json()
    session = SessionState.model_validate(payload)
    assert session.result is not None
    assert isinstance(session.result, Result)


def test_a_result_carries_its_numbers_and_the_thresholds_used(
    client: TestClient, clock: FakeClock
) -> None:
    client.post("/api/v1/session")
    clock.advance(33_500)
    result = Result.model_validate(client.get("/api/v1/session").json()["result"])
    assert result.headline and result.lede
    assert result.details.plv_threshold == pytest.approx(0.60)
    assert [metric.label for metric in result.metrics] == ["Breathing rate", "Rhythm"]
    assert result.thresholds.rr_max == pytest.approx(24.0)


def test_the_trace_is_decimated_to_ten_hertz(client: TestClient, clock: FakeClock) -> None:
    client.post("/api/v1/session")
    clock.advance(33_500)
    trace = Trace.model_validate(client.get("/api/v1/session/trace").json())
    assert len(trace.t) == len(trace.amp) == len(trace.phi_breath)
    assert 295 <= len(trace.t) <= 305
    assert trace.t[0] == pytest.approx(0.0)
    result = client.get("/api/v1/session").json()["result"]
    assert trace.plv == pytest.approx(result["plv"])


def test_an_unclear_result_publishes_no_rate(client: TestClient, clock: FakeClock) -> None:
    client.post("/api/v1/session", params={"scenario": "motion"})
    clock.advance(33_500)
    result = client.get("/api/v1/session").json()["result"]
    assert result["outcome"] == "unclear"
    assert result["rr_bpm"] is None
    assert result["metrics"][0]["value"] == "—"
    assert result["rhythm"] == "Unknown"
