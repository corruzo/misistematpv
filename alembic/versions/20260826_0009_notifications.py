"""Add role-routed real-time notifications.

Revision ID: 20260826_0009
Revises: 20260826_0008
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260826_0009'
down_revision: Union[str, None] = '20260826_0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.notificaciones', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.notificaciones (
            id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_notificaciones PRIMARY KEY,
            usuario_id INT NOT NULL,
            tipo NVARCHAR(40) NOT NULL,
            prioridad NVARCHAR(15) NOT NULL,
            titulo NVARCHAR(150) NOT NULL,
            mensaje NVARCHAR(MAX) NOT NULL,
            creada_en DATETIME2 NOT NULL CONSTRAINT DF_notificaciones_creada_en DEFAULT SYSUTCDATETIME(),
            leida_en DATETIME2 NULL,
            descartada_en DATETIME2 NULL,
            CONSTRAINT FK_notificaciones_usuario FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id),
            CONSTRAINT CK_notificaciones_prioridad CHECK (prioridad IN ('critica', 'advertencia', 'informativa')),
            CONSTRAINT CK_notificaciones_tipo CHECK (tipo IN ('acceso_no_autorizado', 'pase_temporal', 'incidencia_tecnica'))
        );
        CREATE INDEX IX_notificaciones_usuario_id ON dbo.notificaciones(usuario_id, id);
        CREATE INDEX IX_notificaciones_usuario_estado ON dbo.notificaciones(usuario_id, leida_en, descartada_en, id);
    END
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.notificaciones', 'U') IS NOT NULL
        DROP TABLE dbo.notificaciones;
    """)