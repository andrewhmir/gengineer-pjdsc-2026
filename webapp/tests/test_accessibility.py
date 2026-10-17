"""Accessibility floors, asserted rather than trusted.

These are the checks a patient-facing kiosk has to pass: readable type, a big enough action,
visible focus, and status that is never carried by colour alone (REQ-112).
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from hinigram.config import PACKAGE_DIR

CSS = (PACKAGE_DIR / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_every_font_size_is_at_least_sixteen_pixels() -> None:
    sizes = [float(match) for match in re.findall(r"font-size:\s*([0-9.]+)px", CSS)]
    assert sizes, "the stylesheet declares no type sizes at all"
    assert min(sizes) >= 16, f"a patient reads text at {min(sizes)} px"


def test_primary_actions_are_at_least_fifty_six_pixels_tall() -> None:
    block = re.search(r"\.btn\s*\{([^}]*)\}", CSS, re.S)
    assert block is not None, "no .btn rule"
    assert re.search(r"min-height:\s*56px", block.group(1))


def test_focus_is_visible() -> None:
    assert ":focus-visible" in CSS
    assert re.search(r"outline:\s*2px solid var\(--accent\)", CSS)


def test_status_is_never_encoded_by_colour_alone(client: TestClient) -> None:
    body = client.get("/").text
    assert 'id="health-word"' in body
    assert "Station ready" in body or "Checking" in body


def test_the_stylesheet_defines_every_colour_it_uses() -> None:
    """A hex literal outside :root is a colour with no name and no single source."""
    root = re.search(r":root\s*\{(.*?)\}", CSS, re.S)
    assert root is not None
    remainder = CSS.replace(root.group(1), "")
    offenders = re.findall(r"#[0-9a-fA-F]{3,8}\b", remainder)
    assert not offenders, f"hard-coded colours outside :root: {sorted(set(offenders))}"


def test_motion_is_disabled_on_request() -> None:
    assert "prefers-reduced-motion" in CSS
