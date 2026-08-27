"""Add per-user dismissal state for calculated operational alerts.

Revision ID: 20260827_0012
Revises: 20260827_0011
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260827_0012'
down_revision: Union[str, None] = '20260827_0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.alertas_descartadas', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.alertas_descartadas (
            id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_alertas_descartadas PRIMARY KEY,
            usuario_id INT NOT NULL,
            alerta_id NVARCHAR(64) NOT NULL,
            descartada_en DATETIME2 NOT NULL CONSTRAINT DF_alertas_descartadas_fecha DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_alertas_descartadas_usuario FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id),
            CONSTRAINT UX_alertas_descartadas_usuario_alerta UNIQUE (usuario_id, alerta_id)
        );
        CREATE INDEX IX_alertas_descartadas_usuario ON dbo.alertas_descartadas(usuario_id, descartada_en);
    END
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.alertas_descartadas', 'U') IS NOT NULL
        DROP TABLE dbo.alertas_descartadas;
    """)