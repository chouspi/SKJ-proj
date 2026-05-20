from __future__ import annotations

import base64
import json
from enum import StrEnum
from typing import Any

import msgpack


class SerializationFormat(StrEnum):
    JSON = "json"
    MSGPACK = "msgpack"


def _json_default(value: Any) -> Any:
    if isinstance(value, bytes):
        return {
            "__messagebroker_type__": "bytes",
            "base64": base64.b64encode(value).decode("ascii"),
        }
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json_object_hook(value: dict[str, Any]) -> Any:
    if value.get("__messagebroker_type__") == "bytes" and "base64" in value:
        return base64.b64decode(value["base64"].encode("ascii"))
    return value


def encode_message(payload: dict[str, Any], serialization_format: SerializationFormat) -> str | bytes:
    if serialization_format == SerializationFormat.JSON:
        return json.dumps(payload, default=_json_default, separators=(",", ":"))
    return msgpack.packb(payload, use_bin_type=True)


def decode_text_message(payload: str) -> dict[str, Any]:
    return json.loads(payload, object_hook=_json_object_hook)


def decode_binary_message(payload: bytes) -> dict[str, Any]:
    decoded = msgpack.unpackb(payload, raw=False)
    if not isinstance(decoded, dict):
        raise ValueError("Binary message must decode to an object.")
    return decoded


def decode_incoming_frame(frame: dict[str, Any]) -> tuple[SerializationFormat, dict[str, Any]]:
    if frame.get("text") is not None:
        return SerializationFormat.JSON, decode_text_message(frame["text"])
    if frame.get("bytes") is not None:
        return SerializationFormat.MSGPACK, decode_binary_message(frame["bytes"])
    raise ValueError("Unsupported WebSocket frame received.")
