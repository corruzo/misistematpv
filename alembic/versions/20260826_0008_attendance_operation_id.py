"""Add idempotency key for attendance operations.

Revision ID: 20260826_0008
Revises: 20260826_0007
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260826_0008'
down_revision: Union[str, None] = '20260826_0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF COL_LENGTH('dbo.marcajes_asistencia', 'operacion_id') IS NULL
        ALTER TABLE dbo.marcajes_asistencia ADD operacion_id NVARCHAR(64) NULL;
    """)
    op.execute("""
    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = 'UX_marcajes_asistencia_operacion_id'
          AND object_id = OBJECT_ID('dbo.marcajes_asistencia')
    )
        CREATE UNIQUE INDEX UX_marcajes_asistencia_operacion_id
            ON dbo.marcajes_asistencia(operacion_id)
            WHERE operacion_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
    IF EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = 'UX_marcajes_asistencia_operacion_id'
          AND object_id = OBJECT_ID('dbo.marcajes_asistencia')
    )
        DROP INDEX UX_marcajes_asistencia_operacion_id ON dbo.marcajes_asistencia;

    IF COL_LENGTH('dbo.marcajes_asistencia', 'operacion_id') IS NOT NULL
        ALTER TABLE dbo.marcajes_asistencia DROP COLUMN operacion_id;
    """)