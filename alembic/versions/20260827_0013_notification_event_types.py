"""Add global employee, attendance, and reader notification types.

Revision ID: 20260827_0013
Revises: 20260827_0012
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260827_0013'
down_revision: Union[str, None] = '20260827_0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.notificaciones', 'U') IS NOT NULL
    BEGIN
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_notificaciones_tipo' AND parent_object_id = OBJECT_ID('dbo.notificaciones'))
            ALTER TABLE dbo.notificaciones DROP CONSTRAINT CK_notificaciones_tipo;
        ALTER TABLE dbo.notificaciones ADD CONSTRAINT CK_notificaciones_tipo CHECK (tipo IN ('acceso_no_autorizado', 'pase_temporal', 'incidencia_tecnica', 'empleado_registrado', 'empleado_estado_cambiado', 'marcaje_corregido', 'lector_estado_cambiado'));
    END
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.notificaciones', 'U') IS NOT NULL
    BEGIN
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_notificaciones_tipo' AND parent_object_id = OBJECT_ID('dbo.notificaciones'))
            ALTER TABLE dbo.notificaciones DROP CONSTRAINT CK_notificaciones_tipo;
        ALTER TABLE dbo.notificaciones ADD CONSTRAINT CK_notificaciones_tipo CHECK (tipo IN ('acceso_no_autorizado', 'pase_temporal', 'incidencia_tecnica'));
    END
    """)