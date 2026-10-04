"""Unit tests for OpenCV template matching."""

import cv2
import numpy as np
import pytest

from stepwise.services import matcher
from stepwise.services.matcher import find_image_on_screen, match_template_in_frame


def test_match_template_exact() -> None:
    # 500x500 textured canvas
    np.random.seed(42)
    canvas = np.random.randint(50, 200, (500, 500), dtype=np.uint8)

    # Draw high-contrast shapes at (150, 200)
    cv2.rectangle(canvas, (150, 200), (220, 260), 10, -1)
    cv2.putText(canvas, "ERP", (155, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2)

    template = canvas[200:260, 150:220].copy()

    res = match_template_in_frame(canvas, template, confidence_threshold=0.95)
    assert res.found is True
    assert res.confidence >= 0.99
    assert res.top_left_x == 150
    assert res.top_left_y == 200
    assert res.center_x == 185
    assert res.center_y == 230


def test_match_template_with_region() -> None:
    np.random.seed(99)
    canvas = np.random.randint(50, 200, (600, 600), dtype=np.uint8)
    cv2.circle(canvas, (400, 300), 25, 255, -1)
    cv2.circle(canvas, (400, 300), 10, 0, -1)

    template = canvas[275:325, 375:425].copy()

    # Region around (350, 250, 100, 100)
    region = [350, 250, 100, 100]
    res = match_template_in_frame(canvas, template, region=region, confidence_threshold=0.90)
    assert res.found is True
    assert res.top_left_x == 375
    assert res.top_left_y == 275
    assert res.center_x == 400
    assert res.center_y == 300


def test_match_template_not_found() -> None:
    canvas = np.full((300, 300), 255, dtype=np.uint8)
    template = np.zeros((40, 40), dtype=np.uint8)  # Solid black patch (zero variance)

    res = match_template_in_frame(canvas, template, confidence_threshold=0.95)
    assert res.found is False
    assert res.confidence < 0.95


def test_match_template_already_cropped_region() -> None:
    np.random.seed(99)
    canvas = np.random.randint(50, 200, (600, 600), dtype=np.uint8)
    cv2.circle(canvas, (400, 300), 25, 255, -1)
    cv2.circle(canvas, (400, 300), 10, 0, -1)

    template = canvas[275:325, 375:425].copy()
    region = [350, 250, 100, 100]

    # Pre-cropped frame (like capture_screen(region=region)) of dimensions (100, 100)
    cropped_frame = canvas[250:350, 350:450].copy()
    res = match_template_in_frame(cropped_frame, template, region=region, confidence_threshold=0.90)
    assert res.found is True
    assert res.top_left_x == 375
    assert res.top_left_y == 275
    assert res.center_x == 400
    assert res.center_y == 300


def test_match_template_full_frame_same_size_as_region_can_be_disambiguated() -> None:
    """A full frame can coincidentally have the requested region dimensions."""
    rng = np.random.default_rng(123)
    canvas = rng.integers(0, 255, (100, 100), dtype=np.uint8)
    template = canvas[30:50, 40:60].copy()

    res = match_template_in_frame(
        canvas,
        template,
        region=[20, 10, 100, 100],
        confidence_threshold=0.95,
        frame_is_region=False,
    )

    assert res.found is True
    assert res.top_left_x == 40
    assert res.top_left_y == 30
    assert res.center_x == 50
    assert res.center_y == 40


def test_find_image_on_screen_uses_cropped_frame_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = np.random.default_rng(456)
    cropped_frame = rng.integers(0, 255, (80, 90), dtype=np.uint8)
    template = cropped_frame[20:40, 30:50].copy()
    region = [300, 200, 90, 80]

    monkeypatch.setattr(matcher, "load_template_image", lambda path: template)

    def _capture_screen(*, region: list[int] | None = None) -> np.ndarray:
        assert region == [300, 200, 90, 80]
        return cropped_frame

    monkeypatch.setattr(matcher, "capture_screen", _capture_screen)

    res = find_image_on_screen("unused-template.png", confidence=0.95, region=region)

    assert res.found is True
    assert res.top_left_x == 330
    assert res.top_left_y == 220
    assert res.center_x == 340
    assert res.center_y == 230
