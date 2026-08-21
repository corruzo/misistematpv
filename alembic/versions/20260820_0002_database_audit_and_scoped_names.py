"""Scope organization names and add audit records.

Revision ID: 20260820_0002
Revises: 20260820_0001
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260820_0002'
down_revision: Union[str, None] = '20260820_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.departamentos', 'U') IS NOT NULL
    BEGIN
        DECLARE @constraint_name NVARCHAR(256);
        SELECT TOP 1 @constraint_name = QUOTENAME(i.name)
        FROM sys.indexes i
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE i.object_id = OBJECT_ID('dbo.departamentos') AND i.is_unique = 1 AND i.is_unique_constraint = 1 AND c.name = 'nombre';
        IF @constraint_name IS NOT NULL EXEC('ALTER TABLE dbo.departamentos DROP CONSTRAINT ' + @constraint_name);
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_departamentos_gerencia_nombre' AND object_id = OBJECT_ID('dbo.departamentos'))
            CREATE UNIQUE INDEX UX_departamentos_gerencia_nombre ON dbo.departamentos(gerencia_id, nombre);
    END
    IF OBJECT_ID('dbo.cargos', 'U') IS NOT NULL
    BEGIN
        DECLARE @cargo_constraint_name NVARCHAR(256);
        SELECT TOP 1 @cargo_constraint_name = QUOTENAME(i.name)
        FROM sys.indexes i
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE i.object_id = OBJECT_ID('dbo.cargos') AND i.is_unique = 1 AND i.is_unique_constraint = 1 AND c.name = 'nombre';
        IF @cargo_constraint_name IS NOT NULL EXEC('ALTER TABLE dbo.cargos DROP CONSTRAINT ' + @cargo_constraint_name);
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_cargos_departamento_nombre' AND object_id = OBJECT_ID('dbo.cargos'))
            CREATE UNIQUE INDEX UX_cargos_departamento_nombre ON dbo.cargos(departamento_id, nombre);
    END
    IF OBJECT_ID('dbo.auditoria', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.auditoria (
            id INT IDENTITY(1,1) PRIMARY KEY,
            usuario_id INT NULL,
            accion NVARCHAR(50) NOT NULL,
            entidad NVARCHAR(50) NOT NULL,
            entidad_id INT NULL,
            datos_antes NVARCHAR(MAX) NULL,
            datos_despues NVARCHAR(MAX) NULL,
            fecha DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
            CONSTRAINT FK_auditoria_usuario FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id) ON DELETE NO ACTION
        );
        CREATE INDEX IX_auditoria_usuario_fecha ON dbo.auditoria(usuario_id, fecha DESC);
        CREATE INDEX IX_auditoria_entidad_fecha ON dbo.auditoria(entidad, entidad_id, fecha DESC);
    END
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dbo.auditoria")
    op.execute("""
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_departamentos_gerencia_nombre' AND object_id = OBJECT_ID('dbo.departamentos'))
        DROP INDEX UX_departamentos_gerencia_nombre ON dbo.departamentos;
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_cargos_departamento_nombre' AND object_id = OBJECT_ID('dbo.cargos'))
        DROP INDEX UX_cargos_departamento_nombre ON dbo.cargos;
    """)
