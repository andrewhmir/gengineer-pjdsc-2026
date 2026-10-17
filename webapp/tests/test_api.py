"""The HTTP surface: the station page, the session document, and the refusals.

The point of these tests is the contract a browser depends on: one document that describes the
whole station, one Start, and a 409 rather than a second session.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import FakeClock


def test_station_page_returns_html_with_the_disclaimer(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "Research prototype" in body
    assert "not a diagnosis" in body


def test_station_page_references_no_external_host(client: TestClient) -> None:
    """The station must run offline; an external asset would break that promise."""
    body = client.get("/").text
    assert "http://" not in body and "https://" not in body


def test_healthz_reports_the_source(client: TestClient) -> None:
    payload = client.get("/healthz/station").json()
    assert payload["source"] == "sim"
    assert set(payload) == {"ok", "source", "detail", "last_frame_age_ms"}


def test_the_whole_flow_over_http(client: TestClient, clock: FakeClock) -> None:
    assert client.get("/api/v1/session").json()["state"] == "idle"

    started = client.post("/api/v1/session", params={"scenario": "tachypnea"}).json()
    assert started["state"] == "settle"
    assert started["id"].startswith("s-")
    assert started["source"] == "sim"
    assert started["scenario"] == "tachypnea"

    clock.advance(3_200)
    assert client.get("/api/v1/session").json()["state"] == "measuring"

    clock.advance(30_000)
    finished = client.get("/api/v1/session").json()
    assert finished["state"] == "result"
    result = finished["result"]
    assert (result["outcome"], result["rule"]) == ("irregular", "tachypnea")
    assert abs(result["rr_bpm"] - 28.0) <= 2.0

    trace = client.get("/api/v1/session/trace")
    assert trace.status_code == 200
    assert trace.json()["tx_used"] == "tx1"

    assert client.post("/api/v1/session/done").json()["state"] == "idle"


def test_a_second_start_is_refused(client: TestClient) -> None:
    assert client.post("/api/v1/session").status_code == 200
    second = client.post("/api/v1/session")
    assert second.status_code == 409
    assert "not idle" in second.json()["detail"]


def test_done_before_a_result_is_refused(client: TestClient) -> None:
    assert client.post("/api/v1/session/done").status_code == 409


def test_trace_before_a_result_is_refused(client: TestClient) -> None:
    assert client.get("/api/v1/session/trace").status_code == 409


def test_an_unknown_scenario_is_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/session", params={"scenario": "nope"}).status_code == 400


def test_a_scenario_cannot_be_chosen_on_a_recorded_source(make_station) -> None:
    """The demo control only exists on the simulator; a replay must say so, not pretend."""
    from fastapi.testclient import TestClient as Client

    from hinigram.app import create_app

    station = make_station(source="replay")
    with Client(
        create_app(station.settings, station=station, clock=station.clock)
    ) as replay_client:
        response = replay_client.post("/api/v1/session", params={"scenario": "tachypnea"})
        assert response.status_code == 400


def test_the_session_document_carries_no_identifying_fields(client: TestClient) -> None:
    payload = client.get("/api/v1/session").json()
    assert set(payload) == {
        "id",
        "state",
        "source",
        "scenario",
        "started_ms",
        "elapsed_ms",
        "duration_ms",
        "presence",
        "quality",
        "motion",
        "stage_label",
        "chip",
        "steps",
        "live",
        "result",
    }


def test_the_station_returns_to_idle_after_the_result_hold(
    client: TestClient, clock: FakeClock
) -> None:
    client.post("/api/v1/session")
    clock.advance(33_500)
    assert client.get("/api/v1/session").json()["state"] == "result"
    clock.advance(20_100)
    assert client.get("/api/v1/session").json()["state"] == "idle"
