from __future__ import annotations

import asyncio
import logging

import websockets
from pydantic import ValidationError

from .config import Settings
from .protocol import (
    AckPayload,
    DeliverEvent,
    ErrorEvent,
    PublishCommand,
    SubscribeCommand,
    SubscribedEvent,
    WritePayload,
    decode_message,
    encode_message,
)
from .storage import VolumeManager


logger = logging.getLogger(__name__)


class BrokerSubscriber:
    def __init__(self, settings: Settings, volume_manager: VolumeManager) -> None:
        self.settings = settings
        self.volume_manager = volume_manager
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        self._stopped.clear()
        self._task = asyncio.create_task(self._run_forever(), name="haystack-broker-subscriber")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _run_forever(self) -> None:
        while not self._stopped.is_set():
            try:
                async with websockets.connect(self.settings.broker_url, max_size=None) as websocket:
                    await websocket.send(
                        encode_message(SubscribeCommand(topic=self.settings.write_topic).model_dump(mode="json"))
                    )
                    await self._read_loop(websocket)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Broker connection failed: %s", exc)
                await asyncio.sleep(1)

    async def _read_loop(self, websocket: websockets.ClientConnection) -> None:
        while not self._stopped.is_set():
            raw_message = await websocket.recv()
            if not isinstance(raw_message, bytes):
                logger.warning("Ignoring non-binary broker frame.")
                continue

            try:
                decoded_message = decode_message(raw_message)
            except ValueError as exc:
                logger.warning("Ignoring invalid broker event: %s", exc)
                continue

            action = decoded_message.get("action")
            if action == "subscribed":
                try:
                    SubscribedEvent.model_validate(decoded_message)
                except ValidationError as exc:
                    logger.warning("Ignoring invalid subscribe confirmation: %s", exc)
                continue

            if action == "error":
                try:
                    error_event = ErrorEvent.model_validate(decoded_message)
                except ValidationError as exc:
                    logger.warning("Ignoring invalid broker error event: %s", exc)
                else:
                    logger.warning("Broker returned error: %s", error_event.detail)
                continue

            try:
                event = DeliverEvent.model_validate(decoded_message)
            except ValidationError as exc:
                logger.warning("Ignoring invalid broker deliver event: %s", exc)
                continue

            if event.topic != self.settings.write_topic:
                continue

            try:
                write_payload = WritePayload.model_validate(event.payload)
            except ValidationError as exc:
                logger.warning("Ignoring invalid write payload: %s", exc)
                continue

            volume_id, offset, size = await self.volume_manager.append(write_payload.data)
            ack_payload = AckPayload(
                object_id=write_payload.object_id,
                volume_id=volume_id,
                offset=offset,
                size=size,
            )
            await websocket.send(
                encode_message(
                    PublishCommand(
                        topic=self.settings.ack_topic,
                        payload=ack_payload.model_dump(mode="json"),
                    ).model_dump(mode="json")
                )
            )
