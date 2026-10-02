"""Unit tests for OpenCV template matching."""

import cv2
import numpy as np

from stepwise.services.matcher import match_template_in_frame


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


def test_match_template_not_found() -> None:
    canvas = np.full((300, 300), 255, dtype=np.uint8)
    template = np.zeros((40, 40), dtype=np.uint8)  # Solid black patch (zero variance)

    res = match_template_in_frame(canvas, template, confidence_threshold=0.95)
    assert res.found is False
    assert res.confidence < 0.95
