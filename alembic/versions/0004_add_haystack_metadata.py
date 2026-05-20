"""add haystack metadata

Revision ID: 0004_haystack_metadata
Revises: 0003_soft_delete
Create Date: 2026-05-20 00:00:03.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_haystack_metadata"
down_revision = "0003_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stored_files", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"))
        batch_op.add_column(sa.Column("volume_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("offset", sa.Integer(), nullable=True))
        batch_op.alter_column("path", existing_type=sa.String(length=500), nullable=True)
        batch_op.create_index(op.f("ix_stored_files_status"), ["status"], unique=False)
        batch_op.create_index(op.f("ix_stored_files_volume_id"), ["volume_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("stored_files", schema=None) as batch_op:
        batch_op.drop_index(op.f("ix_stored_files_volume_id"))
        batch_op.drop_index(op.f("ix_stored_files_status"))
        batch_op.alter_column("path", existing_type=sa.String(length=500), nullable=False)
        batch_op.drop_column("offset")
        batch_op.drop_column("volume_id")
        batch_op.drop_column("status")
