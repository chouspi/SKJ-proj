from __future__ import annotations

from typing import Any, Literal

import msgpack
from pydantic import BaseModel, Field


class SubscribeCommand(BaseModel):
    action: Literal["subscribe"] = "subscribe"
    topic: str


class PublishCommand(BaseModel):
    action: Literal["publish"] = "publish"
    topic: str
    payload: dict[str, Any]


class DeliverEvent(BaseModel):
    action: Literal["deliver"]
    topic: str
    message_id: int = Field(..., ge=1)
    payload: dict[str, Any]


class ImageJob(BaseModel):
    object_id: str = Field(..., min_length=1)
    bucket_id: int = Field(..., ge=1)
    user_id: str = Field(..., min_length=1)
    operation: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    filename: str = "image"


class ImageDone(BaseModel):
    status: Literal["completed", "failed"]
    object_id: str
    bucket_id: int
    user_id: str
    operation: str
    output_object_id: str | None = None
    error: str | None = None


def encode_message(payload: dict[str, Any]) -> bytes:
    return msgpack.packb(payload, use_bin_type=True)


def decode_message(payload: bytes) -> dict[str, Any]:
    decoded = msgpack.unpackb(payload, raw=False)
    if not isinstance(decoded, dict):
        raise ValueError("MessagePack frame must decode to an object.")
    return decoded
