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


def test_the_closed_page_leaks_no_plv_or_threshold(client: TestClient) -> None:
    """AC-115: both live behind the collapsed staff fold, never in the shell."""
    body = client.get("/").text.lower()
    assert "plv" not in body
    assert "0.60" not in body
    assert "threshold" not in body


def test_patient_copy_is_not_hard_coded_in_the_template(client: TestClient) -> None:
    """The words come from Python, so a test can assert them and the kiosk cannot drift."""
    body = client.get("/").text
    assert "Stand on the mark" not in body
    assert "Irregular breathing" not in body


def test_the_panel_starts_in_a_neutral_loading_state(client: TestClient) -> None:
    assert "Starting the station" in client.get("/").text
