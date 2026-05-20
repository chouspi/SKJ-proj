"""add bucket billing

Revision ID: 0002_bucket_billing
Revises: 0001_buckets
Create Date: 2026-05-20 00:00:01.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_bucket_billing"
down_revision = "0001_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("buckets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bandwidth_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("current_storage_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("ingress_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("egress_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("internal_transfer_bytes", sa.Integer(), nullable=False, server_default="0"))

    connection = op.get_bind()
    stored_files = sa.table(
        "stored_files",
        sa.column("bucket_id", sa.Integer()),
        sa.column("size", sa.Integer()),
    )
    buckets = sa.table(
        "buckets",
        sa.column("id", sa.Integer()),
        sa.column("bandwidth_bytes", sa.Integer()),
        sa.column("current_storage_bytes", sa.Integer()),
        sa.column("ingress_bytes", sa.Integer()),
    )

    totals = connection.execute(
        sa.select(stored_files.c.bucket_id, sa.func.sum(stored_files.c.size))
        .group_by(stored_files.c.bucket_id)
    ).all()
    for bucket_id, total_size in totals:
        total_size = int(total_size or 0)
        connection.execute(
            sa.update(buckets)
            .where(buckets.c.id == bucket_id)
            .values(
                bandwidth_bytes=total_size,
                current_storage_bytes=total_size,
                ingress_bytes=total_size,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("buckets", schema=None) as batch_op:
        batch_op.drop_column("internal_transfer_bytes")
        batch_op.drop_column("egress_bytes")
        batch_op.drop_column("ingress_bytes")
        batch_op.drop_column("current_storage_bytes")
        batch_op.drop_column("bandwidth_bytes")
