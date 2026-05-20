"""add buckets

Revision ID: 0001_buckets
Revises:
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_buckets"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    with op.batch_alter_table("stored_files", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bucket_id", sa.Integer(), nullable=True))

    connection = op.get_bind()
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

    with op.batch_alter_table("stored_files", schema=None) as batch_op:
        batch_op.alter_column("bucket_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(op.f("ix_stored_files_bucket_id"), ["bucket_id"], unique=False)
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
