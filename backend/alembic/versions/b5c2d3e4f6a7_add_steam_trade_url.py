"""add steam_trade_url

Revision ID: b5c2d3e4f6a7
Revises: a3f1c2d4e5b6
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "b5c2d3e4f6a7"
down_revision = "a3f1c2d4e5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("steam_trade_url", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "steam_trade_url")
