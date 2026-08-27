"""Add independent RFID gate agents.

Revision ID: 20260827_0011
Revises: 20260827_0010
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260827_0011'
down_revision: Union[str, None] = '20260827_0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.agentes_garita', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.agentes_garita (
            id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_agentes_garita PRIMARY KEY,
            codigo NVARCHAR(100) NOT NULL,
            nombre NVARCHAR(150) NOT NULL,
            api_key_hash CHAR(64) NOT NULL,
            activo BIT NOT NULL CONSTRAINT DF_agentes_garita_activo DEFAULT 1,
            ultima_conexion DATETIME2 NULL,
            ultimo_heartbeat DATETIME2 NULL,
            version_agente NVARCHAR(40) NULL,
            cola_reportada INT NOT NULL CONSTRAINT DF_agentes_garita_cola DEFAULT 0,
            lector_conectado BIT NOT NULL CONSTRAINT DF_agentes_garita_lector DEFAULT 0,
            creado_en DATETIME2 NOT NULL CONSTRAINT DF_agentes_garita_creado DEFAULT SYSUTCDATETIME(),
            revocado_en DATETIME2 NULL,
            CONSTRAINT UX_agentes_garita_codigo UNIQUE (codigo),
            CONSTRAINT UX_agentes_garita_api_key_hash UNIQUE (api_key_hash),
            CONSTRAINT CK_agentes_garita_cola CHECK (cola_reportada >= 0)
        );
        CREATE INDEX IX_agentes_garita_heartbeat ON dbo.agentes_garita(activo, ultimo_heartbeat);
    END
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.agentes_garita', 'U') IS NOT NULL
        DROP TABLE dbo.agentes_garita;
    """)