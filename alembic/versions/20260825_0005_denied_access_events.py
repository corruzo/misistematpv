"""Persist denied access events for the attendance kiosk.

Revision ID: 20260825_0005
Revises: 20260824_0004
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260825_0005'
down_revision: Union[str, None] = '20260824_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.eventos_acceso_denegado', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.eventos_acceso_denegado (
            id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_eventos_acceso_denegado PRIMARY KEY,
            empleado_id INT NULL,
            empleado_nombre NVARCHAR(200) NOT NULL,
            estado NVARCHAR(20) NOT NULL,
            fecha_hora DATETIME2 NOT NULL CONSTRAINT DF_eventos_acceso_denegado_fecha_hora DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_eventos_acceso_denegado_empleado FOREIGN KEY (empleado_id) REFERENCES dbo.empleados(id)
        );
        CREATE INDEX IX_eventos_acceso_denegado_fecha_id ON dbo.eventos_acceso_denegado(fecha_hora, id);
    END
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.eventos_acceso_denegado', 'U') IS NOT NULL
    BEGIN
        DROP TABLE dbo.eventos_acceso_denegado;
    END
    """)
