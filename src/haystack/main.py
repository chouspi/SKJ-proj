from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from .broker_client import BrokerSubscriber
from .config import settings
from .storage import VolumeManager


volume_manager = VolumeManager(settings.volumes_dir, settings.max_volume_size_bytes)
broker_subscriber = BrokerSubscriber(settings, volume_manager)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await volume_manager.initialize()
    await broker_subscriber.start()
    try:
        yield
    finally:
        await broker_subscriber.stop()
        await volume_manager.close()


app = FastAPI(
    title="Haystack Storage Node",
    description="Append-only storage node for volume-based binary object persistence.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def health() -> dict[str, str | int]:
    return {
        "message": "Haystack storage node is running.",
        "current_volume_id": volume_manager.current_volume_id,
    }


@app.get("/volume/{volume_id}/{offset}/{size}")
async def read_volume_slice(volume_id: int, offset: int, size: int) -> Response:
    if volume_id < 1:
        raise HTTPException(status_code=400, detail="Volume ID must be >= 1.")
    if offset < 0:
        raise HTTPException(status_code=400, detail="Offset must be >= 0.")
    if size < 0:
        raise HTTPException(status_code=400, detail="Size must be >= 0.")

    try:
        data = await volume_manager.read(volume_id, offset, size)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(content=data, media_type="application/octet-stream")
