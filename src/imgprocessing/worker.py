from __future__ import annotations

import asyncio
import logging

import httpx
import websockets
from pydantic import ValidationError

from .config import Settings, settings
from .operations import process_image, processed_filename
from .protocol import DeliverEvent, ImageDone, ImageJob, PublishCommand, SubscribeCommand, decode_message, encode_message


logger = logging.getLogger(__name__)


async def publish_done(websocket: websockets.ClientConnection, settings: Settings, done: ImageDone) -> None:
    await websocket.send(
        encode_message(
            PublishCommand(topic=settings.done_topic, payload=done.model_dump(mode="json")).model_dump(mode="json")
        )
    )


async def handle_job(websocket: websockets.ClientConnection, settings: Settings, job: ImageJob) -> None:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            source = await client.get(
                f"{settings.gateway_base_url.rstrip('/')}/objects/{job.object_id}",
                params={"user_id": job.user_id},
            )
            source.raise_for_status()

            processed = await asyncio.to_thread(process_image, source.content, job.operation, job.params)
            files = {
                "file": (
                    processed_filename(job.filename, job.operation),
                    processed,
                    "image/png",
                )
            }
            upload = await client.post(
                f"{settings.gateway_base_url.rstrip('/')}/files/upload",
                params={"user_id": job.user_id, "bucket_id": job.bucket_id},
                files=files,
            )
            upload.raise_for_status()
            output_object_id = upload.json()["id"]

        await publish_done(
            websocket,
            settings,
            ImageDone(
                status="completed",
                object_id=job.object_id,
                bucket_id=job.bucket_id,
                user_id=job.user_id,
                operation=job.operation,
                output_object_id=output_object_id,
            ),
        )
    except Exception as exc:
        logger.warning("Image job failed for object_id=%s: %s", job.object_id, exc)
        await publish_done(
            websocket,
            settings,
            ImageDone(
                status="failed",
                object_id=job.object_id,
                bucket_id=job.bucket_id,
                user_id=job.user_id,
                operation=job.operation,
                error=str(exc),
            ),
        )


async def run_worker(settings: Settings = settings) -> None:
    while True:
        try:
            async with websockets.connect(settings.broker_url, max_size=None) as websocket:
                await websocket.send(
                    encode_message(SubscribeCommand(topic=settings.jobs_topic).model_dump(mode="json"))
                )
                while True:
                    raw_message = await websocket.recv()
                    if not isinstance(raw_message, bytes):
                        continue
                    try:
                        decoded = decode_message(raw_message)
                        if decoded.get("action") != "deliver":
                            continue
                        event = DeliverEvent.model_validate(decoded)
                        if event.topic != settings.jobs_topic:
                            continue
                        job = ImageJob.model_validate(event.payload)
                    except (ValidationError, ValueError) as exc:
                        logger.warning("Ignoring invalid image job message: %s", exc)
                        continue

                    await handle_job(websocket, settings, job)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Image worker broker connection failed: %s", exc)
            await asyncio.sleep(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
