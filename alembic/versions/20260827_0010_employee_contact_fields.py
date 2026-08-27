"""Add employee contact and emergency contact fields.

Revision ID: 20260827_0010
Revises: 20260826_0009
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260827_0010'
down_revision: Union[str, None] = '20260826_0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for column, definition in (
        ('telefono', 'NVARCHAR(30) NULL'),
        ('email', 'NVARCHAR(254) NULL'),
        ('contacto_emergencia_parentesco', 'NVARCHAR(100) NULL'),
        ('contacto_emergencia_telefono', 'NVARCHAR(30) NULL'),
    ):
        op.execute(f"""
        IF COL_LENGTH('dbo.empleados', '{column}') IS NULL
            ALTER TABLE dbo.empleados ADD {column} {definition};
        """)


def downgrade() -> None:
    for column in ('contacto_emergencia_telefono', 'contacto_emergencia_parentesco', 'email', 'telefono'):
        op.execute(f"""
        IF COL_LENGTH('dbo.empleados', '{column}') IS NOT NULL
            ALTER TABLE dbo.empleados DROP COLUMN {column};
        """)