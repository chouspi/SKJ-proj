"""add soft delete

Revision ID: 0003_soft_delete
Revises: 0002_bucket_billing
Create Date: 2026-05-20 00:00:02.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_soft_delete"
down_revision = "0002_bucket_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stored_files", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index(op.f("ix_stored_files_is_deleted"), ["is_deleted"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("stored_files", schema=None) as batch_op:
        batch_op.drop_index(op.f("ix_stored_files_is_deleted"))
        batch_op.drop_column("is_deleted")
