from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class FilePathInput(BaseModel):
    file_id: UUID = Field(..., description="Unique identifier of the stored file.")


class FileSummary(BaseModel):
    id: UUID
    filename: str = Field(..., min_length=1, max_length=255)
    size: int = Field(..., ge=0)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(FileSummary):
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
