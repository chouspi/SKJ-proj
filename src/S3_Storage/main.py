from __future__ import annotations

import json
import re
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from . import models
    from .database import Base, DATA_DIR, SessionLocal, engine
    from .schemas import (
        DeleteFileResponse,
        ErrorResponse,
        FilePathInput,
        FileSummary,
        FileUploadResponse,
        HealthResponse,
        LegacyFileMetadata,
        UserContext,
        UserIdentifierInput,
    )
except ImportError:
    import models
    from database import Base, DATA_DIR, SessionLocal, engine
    from schemas import (
        DeleteFileResponse,
        ErrorResponse,
        FilePathInput,
        FileSummary,
        FileUploadResponse,
        HealthResponse,
        LegacyFileMetadata,
        UserContext,
        UserIdentifierInput,
    )


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
LEGACY_METADATA_FILE = DATA_DIR / "files_metadata.json"
USER_ID_PATTERN = re.compile(r"[^a-zA-Z0-9._-]")

app = FastAPI(
    title="Mini Object Storage Service",
    description="Object storage backend with file persistence on disk and metadata in SQLite.",
    version="2.0.0",
)


def sanitize_user_id(user_id: str) -> str:
    sanitized = USER_ID_PATTERN.sub("_", user_id.strip())
    if not sanitized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User identifier is required.",
        )
    return sanitized


def ensure_storage_ready() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_identifier_input(
    user_id: str | None = Query(
        None,
        description="User identifier sent as query parameter.",
    ),
    x_user_id: str | None = Header(
        None,
        alias="X-User-Id",
        description="User identifier sent as X-User-Id header.",
    ),
) -> UserIdentifierInput:
    return UserIdentifierInput(user_id=user_id, x_user_id=x_user_id)


def get_user_context(identifier: UserIdentifierInput = Depends(get_user_identifier_input)) -> UserContext:
    if identifier.user_id and identifier.x_user_id:
        if sanitize_user_id(identifier.user_id) != sanitize_user_id(identifier.x_user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conflicting user identifiers. Provide matching user_id and X-User-Id values.",
            )

    resolved_user_id = identifier.x_user_id or identifier.user_id
    if resolved_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing user identifier. Provide X-User-Id header or user_id query parameter.",
        )

    return UserContext(user_id=sanitize_user_id(resolved_user_id))


def get_file_path_input(file_id: str) -> FilePathInput:
    return FilePathInput(file_id=file_id)


def migrate_legacy_metadata(db: Session) -> None:
    if not LEGACY_METADATA_FILE.exists():
        return
    if db.scalar(select(models.StoredFile.id).limit(1)) is not None:
        return

    raw_content = LEGACY_METADATA_FILE.read_text(encoding="utf-8").strip()
    if not raw_content:
        return

    payload = json.loads(raw_content)
    migrated_records: list[models.StoredFile] = []
    for raw_item in payload.values():
        legacy_item = LegacyFileMetadata.model_validate(raw_item)
        migrated_records.append(
            models.StoredFile(
                id=str(legacy_item.id),
                user_id=sanitize_user_id(legacy_item.user_id),
                filename=legacy_item.filename,
                path=legacy_item.path,
                size=legacy_item.size,
                created_at=legacy_item.created_at,
            )
        )

    if migrated_records:
        db.add_all(migrated_records)
        db.commit()


def get_stored_file_or_404(db: Session, file_id: str) -> models.StoredFile:
    stored_file = db.get(models.StoredFile, file_id)
    if stored_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    return stored_file


@app.on_event("startup")
async def on_startup() -> None:
    ensure_storage_ready()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        migrate_legacy_metadata(db)


@app.get(
    "/",
    response_model=HealthResponse,
    summary="Health check",
    response_description="Application status message.",
)
async def root() -> HealthResponse:
    return HealthResponse(message="Object storage service is running.")


@app.post(
    "/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload file",
    response_description="Metadata of the uploaded file.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
    },
)
async def upload_file(
    file: UploadFile = File(..., description="Binary file to upload."),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    file_id = str(uuid4())
    user_storage_dir = STORAGE_DIR / user.user_id
    user_storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_storage_dir / file_id
    size = 0

    try:
        async with aiofiles.open(file_path, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                await output.write(chunk)

        stored_file = models.StoredFile(
            id=file_id,
            user_id=user.user_id,
            filename=file.filename,
            path=str(file_path),
            size=size,
            created_at=datetime.now(timezone.utc),
        )
        db.add(stored_file)
        db.commit()
        db.refresh(stored_file)
    except Exception:
        db.rollback()
        if file_path.exists():
            file_path.unlink()
        raise
    finally:
        await file.close()

    return FileUploadResponse.model_validate(stored_file)


@app.get(
    "/files",
    response_model=list[FileSummary],
    summary="List files",
    response_description="List of files owned by the selected user.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
    },
)
async def list_files(
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> list[FileSummary]:
    statement = (
        select(models.StoredFile)
        .where(models.StoredFile.user_id == user.user_id)
        .order_by(models.StoredFile.created_at.desc())
    )
    stored_files = db.scalars(statement).all()
    return [FileSummary.model_validate(item) for item in stored_files]


@app.get(
    "/files/{file_id}",
    summary="Download file",
    response_description="Binary file content.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "File not found."},
    },
)
async def download_file(
    path_input: FilePathInput = Depends(get_file_path_input),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> FileResponse:
    stored_file = get_stored_file_or_404(db, str(path_input.file_id))
    if stored_file.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    file_path = Path(stored_file.path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file is missing from disk.",
        )

    return FileResponse(
        path=file_path,
        filename=stored_file.filename,
        media_type="application/octet-stream",
    )


@app.delete(
    "/files/{file_id}",
    response_model=DeleteFileResponse,
    summary="Delete file",
    response_description="Deletion confirmation.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "File not found."},
    },
)
async def delete_file(
    path_input: FilePathInput = Depends(get_file_path_input),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> DeleteFileResponse:
    stored_file = get_stored_file_or_404(db, str(path_input.file_id))
    if stored_file.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    file_path = Path(stored_file.path)
    if file_path.exists():
        file_path.unlink()

    db.delete(stored_file)
    db.commit()

    return DeleteFileResponse(id=path_input.file_id, message="File deleted.")
