from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter


TopicName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class SubscribeCommand(BaseModel):
    action: Literal["subscribe"]
    topic: TopicName


class PublishCommand(BaseModel):
    action: Literal["publish"]
    topic: TopicName
    payload: Any


IncomingMessage = Annotated[
    SubscribeCommand | PublishCommand,
    Field(discriminator="action"),
]


incoming_message_adapter = TypeAdapter(IncomingMessage)


class SubscribedEvent(BaseModel):
    action: Literal["subscribed"] = "subscribed"
    topic: TopicName


class DeliverEvent(BaseModel):
    action: Literal["deliver"] = "deliver"
    topic: TopicName
    message_id: int = Field(..., ge=1)
    payload: Any


class ErrorEvent(BaseModel):
    action: Literal["error"] = "error"
    detail: str
