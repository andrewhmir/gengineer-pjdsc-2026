"""The HTTP surface: the station page and the station's own health."""

from __future__ import annotations

from fastapi.testclient import TestClient


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
