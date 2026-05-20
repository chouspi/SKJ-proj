from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from .database import Base
except ImportError:
    from database import Base


class Bucket(Base):
    __tablename__ = "buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    bandwidth_bytes: Mapped[int] = mapped_column(Integer, default=0)
    current_storage_bytes: Mapped[int] = mapped_column(Integer, default=0)
    ingress_bytes: Mapped[int] = mapped_column(Integer, default=0)
    egress_bytes: Mapped[int] = mapped_column(Integer, default=0)
    internal_transfer_bytes: Mapped[int] = mapped_column(Integer, default=0)

    files: Mapped[list["StoredFile"]] = relationship(back_populates="bucket")

    def __repr__(self) -> str:
        return (
            "Bucket("
            f"id={self.id}, user_id={self.user_id}, name={self.name}, "
            f"created_at={self.created_at}, bandwidth_bytes={self.bandwidth_bytes}, "
            f"current_storage_bytes={self.current_storage_bytes}, ingress_bytes={self.ingress_bytes}, "
            f"egress_bytes={self.egress_bytes}, internal_transfer_bytes={self.internal_transfer_bytes}"
            ")"
        )


class StoredFile(Base):
    __tablename__ = "stored_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("buckets.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)
    size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="uploading", index=True)
    volume_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    bucket: Mapped[Bucket] = relationship(back_populates="files")

    def __repr__(self) -> str:
        return (
            "StoredFile("
            f"id={self.id}, user_id={self.user_id}, bucket_id={self.bucket_id}, filename={self.filename}, "
            f"path={self.path}, size={self.size}, status={self.status}, volume_id={self.volume_id}, "
            f"offset={self.offset}, is_deleted={self.is_deleted}, created_at={self.created_at}"
            ")"
        )
