"""add steam_access_token to users

Revision ID: a3f1c2d4e5b6
Revises: 19b84d5ae0e4
Create Date: 2026-04-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a3f1c2d4e5b6'
down_revision: Union[str, None] = '19b84d5ae0e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('steam_access_token', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'steam_access_token')
