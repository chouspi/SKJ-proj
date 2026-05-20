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
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

try:
    from . import models
    from .database import DATA_DIR, SessionLocal, engine
    from .schemas import (
        BucketBillingResponse,
        BucketCreateRequest,
        BucketPathInput,
        BucketSummary,
        DeleteFileResponse,
        ErrorResponse,
        FileListQuery,
        FilePathInput,
        FileSummary,
        FileUploadResponse,
        HealthResponse,
        LegacyFileMetadata,
        TransferContext,
        UploadTargetInput,
        UserContext,
        UserIdentifierInput,
    )
except ImportError:
    import models
    from database import DATA_DIR, SessionLocal, engine
    from schemas import (
        BucketBillingResponse,
        BucketCreateRequest,
        BucketPathInput,
        BucketSummary,
        DeleteFileResponse,
        ErrorResponse,
        FileListQuery,
        FilePathInput,
        FileSummary,
        FileUploadResponse,
        HealthResponse,
        LegacyFileMetadata,
        TransferContext,
        UploadTargetInput,
        UserContext,
        UserIdentifierInput,
    )


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
LEGACY_METADATA_FILE = DATA_DIR / "files_metadata.json"
DEFAULT_BUCKET_PREFIX = "default"
USER_ID_PATTERN = re.compile(r"[^a-zA-Z0-9._-]")

app = FastAPI(
    title="Mini Object Storage Service",
    description="Object storage backend with buckets, billing counters and soft delete.",
    version="3.0.0",
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


def get_transfer_context(
    x_internal_source: bool = Header(
        False,
        alias="X-Internal-Source",
        description="Marks the request as an internal transfer within the cloud.",
    ),
) -> TransferContext:
    return TransferContext(is_internal=x_internal_source)


def get_file_path_input(file_id: str) -> FilePathInput:
    return FilePathInput(file_id=file_id)


def get_bucket_path_input(bucket_id: int) -> BucketPathInput:
    return BucketPathInput(bucket_id=bucket_id)


def get_file_list_query(
    include_deleted: bool = Query(False, description="Include soft-deleted objects in the result."),
) -> FileListQuery:
    return FileListQuery(include_deleted=include_deleted)


def get_upload_target_input(
    bucket_id: int | None = Query(None, ge=1, description="Optional target bucket for the upload."),
) -> UploadTargetInput:
    return UploadTargetInput(bucket_id=bucket_id)


def get_default_bucket_name(user_id: str) -> str:
    return f"{DEFAULT_BUCKET_PREFIX}-{user_id}"


def get_bucket_or_404(db: Session, bucket_id: int) -> models.Bucket:
    bucket = db.get(models.Bucket, bucket_id)
    if bucket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found.")
    return bucket


def ensure_bucket_access(bucket: models.Bucket, user: UserContext) -> None:
    if bucket.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")


def get_or_create_default_bucket(db: Session, user_id: str) -> models.Bucket:
    bucket_name = get_default_bucket_name(user_id)
    bucket = db.scalar(select(models.Bucket).where(models.Bucket.name == bucket_name))
    if bucket is not None:
        return bucket

    bucket = models.Bucket(
        user_id=user_id,
        name=bucket_name,
        created_at=datetime.now(timezone.utc),
    )
    db.add(bucket)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        bucket = db.scalar(select(models.Bucket).where(models.Bucket.name == bucket_name))
        if bucket is None:
            raise
    else:
        db.refresh(bucket)

    return bucket


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
    default_buckets: dict[str, models.Bucket] = {}
    for raw_item in payload.values():
        legacy_item = LegacyFileMetadata.model_validate(raw_item)
        user_id = sanitize_user_id(legacy_item.user_id)
        bucket = default_buckets.get(user_id)
        if bucket is None:
            bucket = get_or_create_default_bucket(db, user_id)
            default_buckets[user_id] = bucket

        migrated_records.append(
            models.StoredFile(
                id=str(legacy_item.id),
                user_id=user_id,
                bucket_id=bucket.id,
                filename=legacy_item.filename,
                path=legacy_item.path,
                size=legacy_item.size,
                is_deleted=False,
                created_at=legacy_item.created_at,
            )
        )

    if migrated_records:
        db.add_all(migrated_records)
        db.commit()


def get_stored_file_or_404(db: Session, file_id: str, *, include_deleted: bool = False) -> models.StoredFile:
    statement = (
        select(models.StoredFile)
        .options(selectinload(models.StoredFile.bucket))
        .where(models.StoredFile.id == file_id)
    )
    if not include_deleted:
        statement = statement.where(models.StoredFile.is_deleted.is_(False))

    stored_file = db.scalar(statement)
    if stored_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    return stored_file


def resolve_upload_bucket(db: Session, user: UserContext, upload_target: UploadTargetInput) -> models.Bucket:
    if upload_target.bucket_id is None:
        return get_or_create_default_bucket(db, user.user_id)

    bucket = get_bucket_or_404(db, upload_target.bucket_id)
    ensure_bucket_access(bucket, user)
    return bucket


def apply_upload_billing(bucket: models.Bucket, size: int, transfer: TransferContext) -> None:
    bucket.bandwidth_bytes += size
    bucket.current_storage_bytes += size
    if transfer.is_internal:
        bucket.internal_transfer_bytes += size
    else:
        bucket.ingress_bytes += size


def apply_download_billing(bucket: models.Bucket, size: int, transfer: TransferContext) -> None:
    bucket.bandwidth_bytes += size
    if transfer.is_internal:
        bucket.internal_transfer_bytes += size
    else:
        bucket.egress_bytes += size


@app.on_event("startup")
async def on_startup() -> None:
    ensure_storage_ready()
    inspector = inspect(engine)
    if inspector.has_table("stored_files") and inspector.has_table("buckets"):
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
    "/buckets/",
    response_model=BucketSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create bucket",
    response_description="Created bucket metadata.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        409: {"model": ErrorResponse, "description": "Bucket name already exists."},
    },
)
async def create_bucket(
    payload: BucketCreateRequest,
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> BucketSummary:
    bucket = models.Bucket(
        user_id=user.user_id,
        name=payload.name,
        created_at=datetime.now(timezone.utc),
    )
    db.add(bucket)
    try:
        db.commit()
        db.refresh(bucket)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bucket name already exists.",
        ) from None

    return BucketSummary.model_validate(bucket)


@app.get(
    "/buckets/",
    response_model=list[BucketSummary],
    summary="List buckets",
    response_description="Buckets owned by the selected user.",
)
async def list_buckets(
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> list[BucketSummary]:
    statement = select(models.Bucket).where(models.Bucket.user_id == user.user_id).order_by(models.Bucket.created_at.desc())
    buckets = db.scalars(statement).all()
    return [BucketSummary.model_validate(bucket) for bucket in buckets]


@app.get(
    "/buckets/{bucket_id}/objects/",
    response_model=list[FileSummary],
    summary="List objects in bucket",
    response_description="Objects stored inside the selected bucket.",
    responses={
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "Bucket not found."},
    },
)
async def list_bucket_objects(
    path_input: BucketPathInput = Depends(get_bucket_path_input),
    filters: FileListQuery = Depends(get_file_list_query),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> list[FileSummary]:
    bucket = get_bucket_or_404(db, path_input.bucket_id)
    ensure_bucket_access(bucket, user)

    statement = (
        select(models.StoredFile)
        .where(models.StoredFile.bucket_id == bucket.id)
        .where(models.StoredFile.user_id == user.user_id)
        .order_by(models.StoredFile.created_at.desc())
    )
    if not filters.include_deleted:
        statement = statement.where(models.StoredFile.is_deleted.is_(False))

    stored_files = db.scalars(statement).all()
    return [FileSummary.model_validate(item) for item in stored_files]


@app.get(
    "/buckets/{bucket_id}/billing/",
    response_model=BucketBillingResponse,
    summary="Get bucket billing",
    response_description="Current transfer and storage counters for the bucket.",
    responses={
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "Bucket not found."},
    },
)
async def get_bucket_billing(
    path_input: BucketPathInput = Depends(get_bucket_path_input),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> BucketBillingResponse:
    bucket = get_bucket_or_404(db, path_input.bucket_id)
    ensure_bucket_access(bucket, user)
    return BucketBillingResponse.model_validate(bucket)


@app.post(
    "/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload file",
    response_description="Metadata of the uploaded file.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "Bucket not found."},
    },
)
async def upload_file(
    file: UploadFile = File(..., description="Binary file to upload."),
    upload_target: UploadTargetInput = Depends(get_upload_target_input),
    transfer: TransferContext = Depends(get_transfer_context),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    bucket = resolve_upload_bucket(db, user, upload_target)
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
            bucket_id=bucket.id,
            filename=file.filename,
            path=str(file_path),
            size=size,
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(stored_file)
        apply_upload_billing(bucket, size, transfer)
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
    filters: FileListQuery = Depends(get_file_list_query),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> list[FileSummary]:
    statement = (
        select(models.StoredFile)
        .where(models.StoredFile.user_id == user.user_id)
        .order_by(models.StoredFile.created_at.desc())
    )
    if not filters.include_deleted:
        statement = statement.where(models.StoredFile.is_deleted.is_(False))

    stored_files = db.scalars(statement).all()
    return [FileSummary.model_validate(item) for item in stored_files]


@app.get(
    "/objects/{file_id}",
    summary="Download object",
    response_description="Binary object content.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "File not found."},
    },
)
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
    transfer: TransferContext = Depends(get_transfer_context),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> FileResponse:
    stored_file = get_stored_file_or_404(db, str(path_input.file_id))
    if stored_file.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    ensure_bucket_access(stored_file.bucket, user)

    file_path = Path(stored_file.path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file is missing from disk.",
        )

    apply_download_billing(stored_file.bucket, stored_file.size, transfer)
    db.commit()

    return FileResponse(
        path=file_path,
        filename=stored_file.filename,
        media_type="application/octet-stream",
    )


@app.delete(
    "/objects/{file_id}",
    response_model=DeleteFileResponse,
    summary="Soft delete object",
    response_description="Deletion confirmation.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "File not found."},
    },
)
@app.delete(
    "/files/{file_id}",
    response_model=DeleteFileResponse,
    summary="Soft delete file",
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
    stored_file = get_stored_file_or_404(db, str(path_input.file_id), include_deleted=True)
    if stored_file.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    ensure_bucket_access(stored_file.bucket, user)

    if stored_file.is_deleted:
        return DeleteFileResponse(id=path_input.file_id, message="File already soft-deleted.")

    stored_file.is_deleted = True
    db.commit()

    return DeleteFileResponse(id=path_input.file_id, message="File soft-deleted.")
