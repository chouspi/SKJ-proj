from __future__ import annotations

from typing import Annotated, Any, Literal

import msgpack
from pydantic import BaseModel, Field, StringConstraints


TopicName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class SubscribeCommand(BaseModel):
    action: Literal["subscribe"] = "subscribe"
    topic: TopicName


class PublishCommand(BaseModel):
    action: Literal["publish"] = "publish"
    topic: TopicName
    payload: dict[str, Any]


class DeliverEvent(BaseModel):
    action: Literal["deliver"]
    topic: TopicName
    message_id: int = Field(..., ge=1)
    payload: dict[str, Any]


class SubscribedEvent(BaseModel):
    action: Literal["subscribed"]
    topic: TopicName


class ErrorEvent(BaseModel):
    action: Literal["error"]
    detail: str


class WritePayload(BaseModel):
    object_id: str = Field(..., min_length=1)
    data: bytes = Field(..., min_length=1)


class AckPayload(BaseModel):
    object_id: str = Field(..., min_length=1)
    volume_id: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    size: int = Field(..., ge=0)


def encode_message(payload: dict[str, Any]) -> bytes:
    return msgpack.packb(payload, use_bin_type=True)


def decode_message(payload: bytes) -> dict[str, Any]:
    decoded = msgpack.unpackb(payload, raw=False)
    if not isinstance(decoded, dict):
        raise ValueError("MessagePack frame must decode to an object.")
    return decoded
