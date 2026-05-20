"""add buckets

Revision ID: 0001_buckets
Revises:
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "0001_buckets"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)

    if not inspector.has_table("buckets"):
        op.create_table(
            "buckets",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_buckets_created_at"), "buckets", ["created_at"], unique=False)
        op.create_index(op.f("ix_buckets_name"), "buckets", ["name"], unique=True)
        op.create_index(op.f("ix_buckets_user_id"), "buckets", ["user_id"], unique=False)

    if not inspector.has_table("stored_files"):
        op.create_table(
            "stored_files",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=100), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("path", sa.String(length=500), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("bucket_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["bucket_id"], ["buckets.id"], name="fk_stored_files_bucket_id_buckets"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("path"),
        )
        op.create_index(op.f("ix_stored_files_bucket_id"), "stored_files", ["bucket_id"], unique=False)
        op.create_index(op.f("ix_stored_files_created_at"), "stored_files", ["created_at"], unique=False)
        op.create_index(op.f("ix_stored_files_user_id"), "stored_files", ["user_id"], unique=False)
        return

    stored_files_columns = {column["name"] for column in inspector.get_columns("stored_files")}
    if "bucket_id" not in stored_files_columns:
        with op.batch_alter_table("stored_files", schema=None) as batch_op:
            batch_op.add_column(sa.Column("bucket_id", sa.Integer(), nullable=True))

    stored_files = sa.table(
        "stored_files",
        sa.column("user_id", sa.String(length=100)),
        sa.column("bucket_id", sa.Integer()),
    )
    buckets = sa.table(
        "buckets",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.String(length=100)),
        sa.column("name", sa.String(length=255)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    user_ids = [
        row[0]
        for row in connection.execute(sa.select(sa.distinct(stored_files.c.user_id))).all()
        if row[0] is not None
    ]
    for user_id in user_ids:
        default_bucket_name = f"default-{user_id}"
        insert_result = connection.execute(
            sa.insert(buckets).values(
                user_id=user_id,
                name=default_bucket_name,
                created_at=datetime.now(timezone.utc),
            )
        )
        bucket_id = insert_result.inserted_primary_key[0]
        connection.execute(
            sa.update(stored_files)
            .where(stored_files.c.user_id == user_id)
            .values(bucket_id=bucket_id)
        )

    indexes = {index["name"] for index in inspector.get_indexes("stored_files")}
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("stored_files")}

    with op.batch_alter_table("stored_files", schema=None) as batch_op:
        batch_op.alter_column("bucket_id", existing_type=sa.Integer(), nullable=False)
        if op.f("ix_stored_files_bucket_id") not in indexes:
            batch_op.create_index(op.f("ix_stored_files_bucket_id"), ["bucket_id"], unique=False)
        if "fk_stored_files_bucket_id_buckets" not in foreign_keys:
            batch_op.create_foreign_key(
                "fk_stored_files_bucket_id_buckets",
                "buckets",
                ["bucket_id"],
                ["id"],
            )


def downgrade() -> None:
    with op.batch_alter_table("stored_files", schema=None) as batch_op:
        batch_op.drop_constraint("fk_stored_files_bucket_id_buckets", type_="foreignkey")
        batch_op.drop_index(op.f("ix_stored_files_bucket_id"))
        batch_op.drop_column("bucket_id")

    op.drop_index(op.f("ix_buckets_user_id"), table_name="buckets")
    op.drop_index(op.f("ix_buckets_name"), table_name="buckets")
    op.drop_index(op.f("ix_buckets_created_at"), table_name="buckets")
    op.drop_table("buckets")
