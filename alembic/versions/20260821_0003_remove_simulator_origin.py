"""Remove the development-only attendance origin."""
from typing import Sequence, Union

from alembic import op


revision: str = '20260821_0003'
down_revision: Union[str, None] = '20260820_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.marcajes_asistencia', 'U') IS NOT NULL
    BEGIN
        IF EXISTS (
            SELECT 1 FROM sys.check_constraints
            WHERE name = 'CK_marcajes_asistencia_origen'
              AND parent_object_id = OBJECT_ID('dbo.marcajes_asistencia')
        )
            ALTER TABLE dbo.marcajes_asistencia DROP CONSTRAINT CK_marcajes_asistencia_origen;
        ALTER TABLE dbo.marcajes_asistencia ADD CONSTRAINT CK_marcajes_asistencia_origen
            CHECK (origen IN ('PUERTO_COM', 'MANUAL_ADMIN'));
    END
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.marcajes_asistencia', 'U') IS NOT NULL
    BEGIN
        IF EXISTS (
            SELECT 1 FROM sys.check_constraints
            WHERE name = 'CK_marcajes_asistencia_origen'
              AND parent_object_id = OBJECT_ID('dbo.marcajes_asistencia')
        )
            ALTER TABLE dbo.marcajes_asistencia DROP CONSTRAINT CK_marcajes_asistencia_origen;
        ALTER TABLE dbo.marcajes_asistencia ADD CONSTRAINT CK_marcajes_asistencia_origen
            CHECK (origen IN ('PUERTO_COM', 'MANUAL_ADMIN', 'SIMULADOR_DEV'));
    END
    """)