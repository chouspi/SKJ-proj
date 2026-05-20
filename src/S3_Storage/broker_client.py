from __future__ import annotations

import asyncio
import logging
from typing import Any

import msgpack
import websockets

try:
    from .database import SessionLocal
    from . import models
    from .settings import Settings
except ImportError:
    from database import SessionLocal
    import models
    from settings import Settings


logger = logging.getLogger(__name__)


def encode_message(payload: dict[str, Any]) -> bytes:
    return msgpack.packb(payload, use_bin_type=True)


def decode_message(payload: bytes) -> dict[str, Any]:
    decoded = msgpack.unpackb(payload, raw=False)
    if not isinstance(decoded, dict):
        raise ValueError("MessagePack frame must decode to an object.")
    return decoded


async def publish_storage_write(settings: Settings, object_id: str, data: bytes) -> None:
    message = {
        "action": "publish",
        "topic": settings.storage_write_topic,
        "payload": {
            "object_id": object_id,
            "data": data,
        },
    }
    async with websockets.connect(settings.broker_url, max_size=None) as websocket:
        await websocket.send(encode_message(message))


class StorageAckListener:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stopped = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._stopped.clear()
        self._task = asyncio.create_task(self._run_forever(), name="s3-storage-ack-listener")

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
                        encode_message(
                            {
                                "action": "subscribe",
                                "topic": self.settings.storage_ack_topic,
                            }
                        )
                    )
                    await self._read_loop(websocket)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Storage ACK listener connection failed: %s", exc)
                await asyncio.sleep(1)

    async def _read_loop(self, websocket: websockets.ClientConnection) -> None:
        while not self._stopped.is_set():
            raw_message = await websocket.recv()
            if not isinstance(raw_message, bytes):
                continue

            try:
                event = decode_message(raw_message)
            except ValueError as exc:
                logger.warning("Invalid ACK broker event: %s", exc)
                continue

            if event.get("action") != "deliver" or event.get("topic") != self.settings.storage_ack_topic:
                continue

            payload = event.get("payload")
            if not isinstance(payload, dict):
                logger.warning("Invalid ACK payload: %r", payload)
                continue

            await asyncio.to_thread(apply_storage_ack, payload)


def apply_storage_ack(payload: dict[str, Any]) -> None:
    object_id = str(payload.get("object_id", ""))
    volume_id = payload.get("volume_id")
    offset = payload.get("offset")
    size = payload.get("size")

    if not object_id or not isinstance(volume_id, int) or not isinstance(offset, int) or not isinstance(size, int):
        logger.warning("Ignoring malformed storage ACK: %r", payload)
        return

    with SessionLocal() as db:
        stored_file = db.get(models.StoredFile, object_id)
        if stored_file is None:
            logger.warning("ACK references unknown object_id=%s", object_id)
            return

        if stored_file.status == "ready":
            return

        bucket = db.get(models.Bucket, stored_file.bucket_id)
        stored_file.volume_id = volume_id
        stored_file.offset = offset
        stored_file.size = size
        stored_file.status = "ready"

        if bucket is not None:
            bucket.bandwidth_bytes += size
            bucket.current_storage_bytes += size
            bucket.ingress_bytes += size

        db.commit()
