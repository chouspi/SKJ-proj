from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.imgprocessing.operations import process_image


def make_test_image() -> bytes:
    image = Image.new("RGB", (8, 8), color=(120, 80, 40))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize(
    ("operation", "params"),
    [
        ("negative", {}),
        ("mirror", {}),
        ("crop", {"x": 1, "y": 1, "width": 4, "height": 4}),
        ("brightness", {"amount": 50}),
        ("grayscale", {}),
    ],
)
def test_supported_operations_return_png(operation: str, params: dict[str, int]) -> None:
    output = process_image(make_test_image(), operation, params)
    assert output.startswith(b"\x89PNG")


def test_invalid_operation_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unsupported image operation"):
        process_image(make_test_image(), "expoit-op", {})


def test_crop_outside_image_raises_value_error() -> None:
    with pytest.raises(ValueError, match="exceeds image bounds"):
        process_image(make_test_image(), "crop", {"x": 5, "y": 5, "width": 8, "height": 8})
