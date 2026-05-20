from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    message: str = Field(..., description="Human readable health-check message.")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error detail returned by the API.")


class UserIdentifierInput(BaseModel):
    user_id: str | None = Field(
        None,
        title="User ID",
        description="User identifier sent as query parameter.",
        examples=["alice"],
    )
    x_user_id: str | None = Field(
        None,
        title="X-User-Id",
        description="User identifier sent as X-User-Id header.",
        examples=["alice"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "alice",
                "x_user_id": None,
            }
        }
    )


class UserContext(BaseModel):
    user_id: str = Field(
        ...,
        title="Resolved User ID",
        description="Sanitized identifier used for storage ownership.",
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._-]+$",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "alice",
            }
        }
    )


class TransferContext(BaseModel):
    is_internal: bool = Field(False, description="Whether the transfer is internal to the cloud.")


class FilePathInput(BaseModel):
    file_id: UUID = Field(..., description="Unique identifier of the stored file.")


class BucketPathInput(BaseModel):
    bucket_id: int = Field(..., ge=1, description="Numeric identifier of the bucket.")


class BucketCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Globally unique bucket name.")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Bucket name must not be empty.")
        return cleaned


class BucketSummary(BaseModel):
    id: int
    user_id: str
    name: str
    created_at: datetime
    bandwidth_bytes: int = Field(..., ge=0)
    current_storage_bytes: int = Field(..., ge=0)
    ingress_bytes: int = Field(..., ge=0)
    egress_bytes: int = Field(..., ge=0)
    internal_transfer_bytes: int = Field(..., ge=0)

    model_config = ConfigDict(from_attributes=True)


class BucketBillingResponse(BucketSummary):
    pass


class FileListQuery(BaseModel):
    include_deleted: bool = Field(False, description="Include soft-deleted objects in the result.")


class UploadTargetInput(BaseModel):
    bucket_id: int | None = Field(None, ge=1, description="Target bucket identifier.")


class FileSummary(BaseModel):
    id: UUID
    bucket_id: int = Field(..., ge=1)
    filename: str = Field(..., min_length=1, max_length=255)
    size: int = Field(..., ge=0)
    status: str
    volume_id: int | None = Field(None, ge=1)
    offset: int | None = Field(None, ge=0)
    is_deleted: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(FileSummary):
    pass


class ImageProcessRequest(BaseModel):
    operation: str = Field(..., min_length=1, max_length=64)
    params: dict[str, int | float | str | bool] = Field(default_factory=dict)


class ImageProcessResponse(BaseModel):
    status: str
    object_id: UUID
    bucket_id: int
    operation: str


class CompactionObject(BaseModel):
    object_id: UUID
    volume_id: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    size: int = Field(..., ge=0)


class CompactionLocationUpdate(BaseModel):
    volume_id: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    size: int = Field(..., ge=0)


class CompactionLocationResponse(CompactionObject):
    pass


class DeleteFileResponse(BaseModel):
    id: UUID
    message: str = Field(..., description="Deletion result.")


class LegacyFileMetadata(BaseModel):
    id: UUID
    user_id: str
    filename: str
    path: str
    size: int = Field(..., ge=0)
    created_at: datetime
