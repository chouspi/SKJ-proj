from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
METADATA_FILE = DATA_DIR / "files_metadata.json"
USER_ID_PATTERN = re.compile(r"[^a-zA-Z0-9._-]")
metadata_lock = asyncio.Lock()


class FileMetadata(BaseModel):
    id: str
    user_id: str
    filename: str
    path: str
    size: int
    created_at: str


class FileSummary(BaseModel):
    id: str
    filename: str
    size: int
    created_at: str


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    size: int


def sanitize_user_id(user_id: str) -> str:
    sanitized = USER_ID_PATTERN.sub("_", user_id.strip())
    if not sanitized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User identifier is required.",
        )
    return sanitized


async def ensure_storage_ready() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not METADATA_FILE.exists():
        METADATA_FILE.write_text("{}", encoding="utf-8")


async def load_metadata_unlocked() -> dict[str, dict[str, Any]]:
    async with aiofiles.open(METADATA_FILE, "r", encoding="utf-8") as handle:
        raw = await handle.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


async def save_metadata_unlocked(payload: dict[str, dict[str, Any]]) -> None:
    async with aiofiles.open(METADATA_FILE, "w", encoding="utf-8") as handle:
        await handle.write(json.dumps(payload, indent=2))


async def get_current_user_id(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    user_id: str | None = Query(None),
) -> str:
    resolved_user_id = x_user_id if x_user_id is not None else user_id
    if resolved_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing user identifier. Provide X-User-Id header or user_id query parameter.",
        )
    sanitized = sanitize_user_id(resolved_user_id)
    return sanitized


app = FastAPI(
    title="Mini Object Storage Service",
    description="Minimal object storage backend for file upload, download, listing and deletion.",
    version="1.0.0",
)


@app.on_event("startup")
async def on_startup() -> None:
    await ensure_storage_ready()


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Object storage service is running."}


@app.post("/files/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
) -> FileUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    file_id = str(uuid4())
    user_storage_dir = STORAGE_DIR / user_id
    user_storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_storage_dir / file_id

    size = 0
    async with aiofiles.open(file_path, "wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            await output.write(chunk)
    await file.close()

    async with metadata_lock:
        metadata = await load_metadata_unlocked()
        metadata[file_id] = FileMetadata(
            id=file_id,
            user_id=user_id,
            filename=file.filename,
            path=str(file_path),
            size=size,
            created_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump()
        await save_metadata_unlocked(metadata)

    return FileUploadResponse(id=file_id, filename=file.filename, size=size)


@app.get("/files", response_model=list[FileSummary])
async def list_files(user_id: str = Depends(get_current_user_id)) -> list[FileSummary]:
    async with metadata_lock:
        metadata = await load_metadata_unlocked()
    return [
        FileSummary(
            id=item["id"],
            filename=item["filename"],
            size=item["size"],
            created_at=item["created_at"],
        )
        for item in metadata.values()
        if item["user_id"] == user_id
    ]


@app.get("/files/{file_id}")
async def download_file(file_id: str, user_id: str = Depends(get_current_user_id)) -> FileResponse:
    async with metadata_lock:
        metadata = await load_metadata_unlocked()
        file_record = metadata.get(file_id)
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    if file_record["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    file_path = Path(file_record["path"])
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file is missing from disk.",
        )

    return FileResponse(
        path=file_path,
        filename=file_record["filename"],
        media_type="application/octet-stream",
    )


@app.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_file(file_id: str, user_id: str = Depends(get_current_user_id)) -> Response:
    async with metadata_lock:
        metadata = await load_metadata_unlocked()
        file_record = metadata.get(file_id)
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
        if file_record["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        file_path = Path(file_record["path"])
        if file_path.exists():
            file_path.unlink()
        metadata.pop(file_id, None)
        await save_metadata_unlocked(metadata)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
