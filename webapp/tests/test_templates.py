"""Template-level guarantees: what the shell promises before any JavaScript runs."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_station_page_carries_the_no_camera_caption(client: TestClient) -> None:
    """REQ-119: the figure is a guide, not an image of the person."""
    body = client.get("/").text
    assert "abstract guide" in body
    assert "not a camera" in body


def test_station_page_links_its_own_stylesheet(client: TestClient) -> None:
    body = client.get("/").text
    assert "/static/css/app.css" in body


def test_the_panel_is_a_live_region(client: TestClient) -> None:
    """State changes must reach a screen reader once the client renders them."""
    assert 'aria-live="polite"' in client.get("/").text


def test_the_page_declares_english(client: TestClient) -> None:
    assert '<html lang="en">' in client.get("/").text


def test_the_source_is_named_before_javascript_runs(client: TestClient) -> None:
    """REQ-103: simulated data must never look live, even if the client script fails."""
    body = client.get("/").text
    assert 'id="source-chip"' in body
    assert "SIM" in body
