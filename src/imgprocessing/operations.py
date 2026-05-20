from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def process_image(image_bytes: bytes, operation: str, params: dict[str, Any]) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    img_array = np.array(image)
    operation = operation.strip().lower()

    if operation in {"negative", "invert", "inversion"}:
        new_array = 255 - img_array
        return encode_png(new_array)

    if operation in {"mirror", "flip_horizontal", "horizontal_flip"}:
        new_array = img_array[:, ::-1, :]
        return encode_png(new_array)

    if operation == "crop":
        new_array = crop(img_array, params)
        return encode_png(new_array)

    if operation in {"brightness", "brighten"}:
        amount = int(params.get("amount", 50))
        new_array = np.clip(img_array.astype(np.int16) + amount, 0, 255).astype(np.uint8)
        return encode_png(new_array)

    if operation == "grayscale":
        rgb = img_array.astype(np.float32)
        gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.uint8)
        return encode_png(gray)

    raise ValueError(f"Unsupported image operation: {operation}")


def crop(img_array: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    height, width = img_array.shape[:2]
    x = int(params.get("x", 0))
    y = int(params.get("y", 0))
    crop_width = int(params.get("width", width))
    crop_height = int(params.get("height", height))

    if x < 0 or y < 0 or crop_width <= 0 or crop_height <= 0:
        raise ValueError("Crop parameters must be positive and inside image bounds.")
    if x + crop_width > width or y + crop_height > height:
        raise ValueError("Crop rectangle exceeds image bounds.")

    return img_array[y : y + crop_height, x : x + crop_width, :]


def encode_png(img_array: np.ndarray) -> bytes:
    output = BytesIO()
    Image.fromarray(img_array).save(output, format="PNG")
    return output.getvalue()


def processed_filename(filename: str, operation: str) -> str:
    stem = Path(filename).stem or "image"
    return f"{stem}_{operation}.png"
