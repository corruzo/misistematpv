"""Baseline for the existing SQL Server schema.

Revision ID: 20260820_0001
Revises:
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260820_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
