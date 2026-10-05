"""media: optional object storage (Cloudflare R2)

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("media", sa.Column("storage_key", sa.String(length=200), nullable=True))
    op.alter_column("media", "data", existing_type=sa.LargeBinary(), nullable=True)
    op.create_check_constraint("ck_media_has_content", "media", "data IS NOT NULL OR storage_key IS NOT NULL")


def downgrade() -> None:
    # Images that only exist in the bucket cannot be represented without object storage.
    op.execute("DELETE FROM media WHERE data IS NULL")
    op.drop_constraint("ck_media_has_content", "media", type_="check")
    op.alter_column("media", "data", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_column("media", "storage_key")
