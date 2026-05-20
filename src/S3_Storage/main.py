from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

try:
    from . import models
    from .broker_client import StorageAckListener, publish_image_job, publish_storage_write
    from .database import DATA_DIR, SessionLocal, engine
    from .schemas import (
        BucketBillingResponse,
        BucketCreateRequest,
        BucketPathInput,
        BucketSummary,
        CompactionLocationResponse,
        CompactionLocationUpdate,
        CompactionObject,
        DeleteFileResponse,
        ErrorResponse,
        FileListQuery,
        FilePathInput,
        FileSummary,
        FileUploadResponse,
        HealthResponse,
        ImageProcessRequest,
        ImageProcessResponse,
        LegacyFileMetadata,
        ServiceHealthResponse,
        SystemDashboardResponse,
        SystemStatsResponse,
        TransferContext,
        UploadTargetInput,
        UserContext,
        UserIdentifierInput,
    )
    from .settings import settings
except ImportError:
    import models
    from broker_client import StorageAckListener, publish_image_job, publish_storage_write
    from database import DATA_DIR, SessionLocal, engine
    from schemas import (
        BucketBillingResponse,
        BucketCreateRequest,
        BucketPathInput,
        BucketSummary,
        CompactionLocationResponse,
        CompactionLocationUpdate,
        CompactionObject,
        DeleteFileResponse,
        ErrorResponse,
        FileListQuery,
        FilePathInput,
        FileSummary,
        FileUploadResponse,
        HealthResponse,
        ImageProcessRequest,
        ImageProcessResponse,
        LegacyFileMetadata,
        ServiceHealthResponse,
        SystemDashboardResponse,
        SystemStatsResponse,
        TransferContext,
        UploadTargetInput,
        UserContext,
        UserIdentifierInput,
    )
    from settings import settings


BASE_DIR = Path(__file__).resolve().parent
LEGACY_METADATA_FILE = DATA_DIR / "files_metadata.json"
DEFAULT_BUCKET_PREFIX = "default"
USER_ID_PATTERN = re.compile(r"[^a-zA-Z0-9._-]")

app = FastAPI(
    title="Mini Object Storage Service",
    description="S3 Gateway with bucket metadata, billing, soft delete and Haystack-backed storage.",
    version="4.0.0",
)
storage_ack_listener = StorageAckListener(settings)


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
                status="ready",
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
    await storage_ack_listener.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await storage_ack_listener.stop()


@app.get(
    "/",
    response_model=HealthResponse,
    summary="Health check",
    response_description="Application status message.",
)
async def root() -> HealthResponse:
    return HealthResponse(message="Object storage service is running.")


async def check_service_health(url: str, timeout: float = 2.0) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            return "healthy" if response.status_code < 500 else "unhealthy"
    except Exception:
        return "unreachable"


@app.get(
    "/system/stats",
    response_model=SystemDashboardResponse,
    summary="System dashboard statistics",
    response_description="Aggregated system statistics and service health statuses.",
)
async def system_stats(db: Session = Depends(get_db)) -> SystemDashboardResponse:
    broker_url = "http://127.0.0.1:8001/"
    haystack_url = f"{settings.haystack_base_url.rstrip('/')}/"
    image_worker_url = "http://127.0.0.1:8003/"

    s3_status = "healthy"
    broker_status, haystack_status, image_status = await asyncio.gather(
        check_service_health(broker_url),
        check_service_health(haystack_url),
        check_service_health(image_worker_url),
    )

    total_result = db.execute(select(func.count(models.StoredFile.id)))
    total_objects = total_result.scalar() or 0

    uploading_result = db.execute(
        select(func.count(models.StoredFile.id)).where(models.StoredFile.status == "uploading")
    )
    uploading = uploading_result.scalar() or 0

    ready_result = db.execute(
        select(func.count(models.StoredFile.id)).where(models.StoredFile.status == "ready")
    )
    ready = ready_result.scalar() or 0

    deleted_result = db.execute(
        select(func.count(models.StoredFile.id)).where(models.StoredFile.is_deleted.is_(True))
    )
    deleted = deleted_result.scalar() or 0

    volume_result = db.execute(
        select(func.count(models.StoredFile.volume_id.distinct())).where(models.StoredFile.volume_id.is_not(None))
    )
    volume_count = volume_result.scalar() or 0

    size_result = db.execute(
        select(func.coalesce(func.sum(models.StoredFile.size), 0))
    )
    total_size_bytes = size_result.scalar() or 0

    return SystemDashboardResponse(
        services=ServiceHealthResponse(
            s3_gateway=s3_status,
            message_broker=broker_status,
            haystack_node=haystack_status,
            image_processing=image_status,
        ),
        stats=SystemStatsResponse(
            total_objects=total_objects,
            uploading=uploading,
            ready=ready,
            deleted=deleted,
            volume_count=volume_count,
            total_size_bytes=total_size_bytes,
        ),
    )


@app.get("/system/volumes")
async def system_volumes(db: Session = Depends(get_db)) -> dict:
    haystack_url = f"{settings.haystack_base_url.rstrip('/')}/volumes"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(haystack_url, timeout=5)
            resp.raise_for_status()
            haystack_data = resp.json()
    except Exception:
        haystack_data = {"max_volume_size_bytes": 0, "volumes": []}

    max_size = haystack_data.get("max_volume_size_bytes", 0)
    volume_file_sizes = {v["id"]: v["file_size_bytes"] for v in haystack_data.get("volumes", [])}

    volume_ids = [
        row[0]
        for row in db.execute(
            select(models.StoredFile.volume_id)
            .where(models.StoredFile.volume_id.is_not(None))
            .distinct()
            .order_by(models.StoredFile.volume_id)
        ).all()
    ]

    results = []
    for vid in volume_ids:
        total_q = db.execute(
            select(func.count(models.StoredFile.id))
            .where(models.StoredFile.volume_id == vid)
        )
        total_objects = total_q.scalar() or 0

        active_q = db.execute(
            select(func.count(models.StoredFile.id))
            .where(models.StoredFile.volume_id == vid)
            .where(models.StoredFile.is_deleted.is_(False))
        )
        active_objects = active_q.scalar() or 0

        deleted_q = db.execute(
            select(func.count(models.StoredFile.id))
            .where(models.StoredFile.volume_id == vid)
            .where(models.StoredFile.is_deleted.is_(True))
        )
        deleted_objects = deleted_q.scalar() or 0

        size_q = db.execute(
            select(func.coalesce(func.sum(models.StoredFile.size), 0))
            .where(models.StoredFile.volume_id == vid)
        )
        total_data_bytes = size_q.scalar() or 0

        file_size = volume_file_sizes.get(vid, 0)
        usage_pct = round((file_size / max_size * 100) if max_size > 0 else 0, 1)
        fragmentation = round((1 - total_data_bytes / file_size) * 100, 1) if file_size > 0 else 0.0

        results.append({
            "volume_id": vid,
            "name": f"volume_{vid}.dat",
            "file_size_bytes": file_size,
            "max_size_bytes": max_size,
            "usage_pct": usage_pct,
            "total_objects": total_objects,
            "active_objects": active_objects,
            "deleted_objects": deleted_objects,
            "fragmentation_pct": fragmentation,
        })

    return {"volumes": results}


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
    "/buckets/{bucket_id}/objects/{file_id}/process",
    response_model=ImageProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start image processing job",
    response_description="Image processing job dispatch confirmation.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "Bucket or file not found."},
        409: {"model": ErrorResponse, "description": "File is not ready."},
    },
)
async def process_object(
    payload: ImageProcessRequest,
    path_input: BucketPathInput = Depends(get_bucket_path_input),
    file_input: FilePathInput = Depends(get_file_path_input),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> ImageProcessResponse:
    bucket = get_bucket_or_404(db, path_input.bucket_id)
    ensure_bucket_access(bucket, user)
    stored_file = get_stored_file_or_404(db, str(file_input.file_id))

    if stored_file.bucket_id != bucket.id or stored_file.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    if stored_file.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File is not ready yet. Current status: {stored_file.status}.",
        )

    await publish_image_job(
        settings,
        {
            "object_id": stored_file.id,
            "bucket_id": bucket.id,
            "user_id": user.user_id,
            "operation": payload.operation,
            "params": payload.params,
            "filename": stored_file.filename,
        },
    )

    return ImageProcessResponse(
        status="processing_started",
        object_id=file_input.file_id,
        bucket_id=bucket.id,
        operation=payload.operation,
    )


@app.get(
    "/internal/volumes/{volume_id}/objects",
    response_model=list[CompactionObject],
    summary="List live objects for volume compaction",
)
async def list_live_volume_objects(
    volume_id: int,
    db: Session = Depends(get_db),
) -> list[CompactionObject]:
    if volume_id < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Volume ID must be >= 1.")

    statement = (
        select(models.StoredFile)
        .where(models.StoredFile.volume_id == volume_id)
        .where(models.StoredFile.status == "ready")
        .where(models.StoredFile.is_deleted.is_(False))
        .where(models.StoredFile.offset.is_not(None))
        .order_by(models.StoredFile.offset.asc())
    )
    stored_files = db.scalars(statement).all()
    return [
        CompactionObject(
            object_id=item.id,
            volume_id=item.volume_id or volume_id,
            offset=item.offset or 0,
            size=item.size,
        )
        for item in stored_files
    ]


@app.patch(
    "/internal/objects/{file_id}/location",
    response_model=CompactionLocationResponse,
    summary="Update object Haystack location after compaction",
)
async def update_object_location(
    payload: CompactionLocationUpdate,
    path_input: FilePathInput = Depends(get_file_path_input),
    db: Session = Depends(get_db),
) -> CompactionLocationResponse:
    stored_file = db.get(models.StoredFile, str(path_input.file_id))
    if stored_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    stored_file.volume_id = payload.volume_id
    stored_file.offset = payload.offset
    stored_file.size = payload.size
    stored_file.status = "ready"
    db.commit()

    return CompactionLocationResponse(
        object_id=path_input.file_id,
        volume_id=payload.volume_id,
        offset=payload.offset,
        size=payload.size,
    )


@app.get(
    "/upload/{file_id}",
    response_model=FileSummary,
    summary="Get upload status",
    response_description="Current status of the uploaded file.",
    responses={
        404: {"model": ErrorResponse, "description": "File not found."},
    },
)
async def get_upload_status(
    path_input: FilePathInput = Depends(get_file_path_input),
    user: UserContext = Depends(get_user_context),
    db: Session = Depends(get_db),
) -> FileSummary:
    stored_file = get_stored_file_or_404(db, str(path_input.file_id), include_deleted=True)
    if stored_file.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return FileSummary.model_validate(stored_file)


@app.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload file",
    response_description="Metadata of the accepted file upload.",
    include_in_schema=False,
)
@app.post(
    "/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload file",
    response_description="Metadata of the accepted file upload.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request."},
        403: {"model": ErrorResponse, "description": "Access denied."},
        404: {"model": ErrorResponse, "description": "Bucket not found."},
    },
)
async def upload_file(
    file: UploadFile = File(..., description="Binary file to upload."),
    upload_target: UploadTargetInput = Depends(get_upload_target_input),
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
    data = await file.read()
    size = len(data)
    if size == 0:
        await file.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must not be empty.")

    try:
        stored_file = models.StoredFile(
            id=file_id,
            user_id=user.user_id,
            bucket_id=bucket.id,
            filename=file.filename,
            path=None,
            size=size,
            status="uploading",
            volume_id=None,
            offset=None,
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(stored_file)
        db.commit()
        db.refresh(stored_file)

        try:
            await publish_storage_write(settings, file_id, data)
        except Exception as exc:
            stored_file.status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Message broker is unavailable; upload was not dispatched.",
            ) from exc
    except Exception:
        db.rollback()
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
    "/download/{file_id}",
    summary="Download object",
    response_description="Binary object content.",
    include_in_schema=False,
)
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
) -> Response:
    stored_file = get_stored_file_or_404(db, str(path_input.file_id))
    if stored_file.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    ensure_bucket_access(stored_file.bucket, user)

    if stored_file.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File is not ready yet. Current status: {stored_file.status}.",
        )
    if stored_file.volume_id is None or stored_file.offset is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="File has no Haystack location.")

    haystack_url = (
        f"{settings.haystack_base_url.rstrip('/')}/volume/"
        f"{stored_file.volume_id}/{stored_file.offset}/{stored_file.size}"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        haystack_response = await client.get(haystack_url)
    if haystack_response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file is missing in Haystack.")
    if haystack_response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Haystack read failed.")

    apply_download_billing(stored_file.bucket, stored_file.size, transfer)
    db.commit()

    return Response(
        content=haystack_response.content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{stored_file.filename}"'},
    )


@app.delete(
    "/download/{file_id}",
    response_model=DeleteFileResponse,
    summary="Soft delete object",
    response_description="Deletion confirmation.",
    include_in_schema=False,
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
