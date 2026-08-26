"""Migrate to definitive three-role system (Desarrollador, RRHH, Inspector).

Revision ID: 20260825_0006
Revises: 20260825_0005
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260825_0006'
down_revision: Union[str, None] = '20260825_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.usuarios', 'U') IS NOT NULL
    BEGIN
        IF EXISTS (
            SELECT 1 FROM sys.check_constraints
            WHERE name = 'CK_usuarios_rol'
              AND parent_object_id = OBJECT_ID('dbo.usuarios')
        )
            ALTER TABLE dbo.usuarios DROP CONSTRAINT CK_usuarios_rol;

        -- Map old roles to new ones
        UPDATE dbo.usuarios SET rol = 'Desarrollador' WHERE rol IN ('Administrador', 'Sistemas');
        UPDATE dbo.usuarios SET rol = 'Inspector' WHERE rol = 'Consulta';
        UPDATE dbo.usuarios SET rol = 'Inspector' WHERE rol IS NULL OR rol NOT IN ('Desarrollador', 'RRHH', 'Inspector');

        -- Apply default change
        IF EXISTS (SELECT 1 FROM sys.default_constraints WHERE name LIKE '%rol%' AND parent_object_id = OBJECT_ID('dbo.usuarios'))
        BEGIN
            DECLARE @df_name NVARCHAR(256);
            SELECT @df_name = name FROM sys.default_constraints WHERE parent_object_id = OBJECT_ID('dbo.usuarios') AND parent_column_id = (SELECT column_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.usuarios') AND name = 'rol');
            IF @df_name IS NOT NULL
                EXEC('ALTER TABLE dbo.usuarios DROP CONSTRAINT ' + @df_name);
        END
        ALTER TABLE dbo.usuarios ADD DEFAULT 'Desarrollador' FOR rol;

        ALTER TABLE dbo.usuarios ADD CONSTRAINT CK_usuarios_rol
            CHECK (rol IN ('Desarrollador', 'RRHH', 'Inspector'));
    END
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.usuarios', 'U') IS NOT NULL
    BEGIN
        -- Revert role names
        UPDATE dbo.usuarios SET rol = 'Administrador' WHERE rol = 'Desarrollador';
        UPDATE dbo.usuarios SET rol = 'Consulta' WHERE rol = 'Inspector';

        IF EXISTS (
            SELECT 1 FROM sys.check_constraints
            WHERE name = 'CK_usuarios_rol'
              AND parent_object_id = OBJECT_ID('dbo.usuarios')
        )
            ALTER TABLE dbo.usuarios DROP CONSTRAINT CK_usuarios_rol;

        -- Apply old default
        IF EXISTS (SELECT 1 FROM sys.default_constraints WHERE parent_object_id = OBJECT_ID('dbo.usuarios') AND parent_column_id = (SELECT column_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.usuarios') AND name = 'rol'))
        BEGIN
            DECLARE @df_name NVARCHAR(256);
            SELECT @df_name = name FROM sys.default_constraints WHERE parent_object_id = OBJECT_ID('dbo.usuarios') AND parent_column_id = (SELECT column_id FROM sys.columns WHERE object_id = OBJECT_ID('dbo.usuarios') AND name = 'rol');
            IF @df_name IS NOT NULL
                EXEC('ALTER TABLE dbo.usuarios DROP CONSTRAINT ' + @df_name);
        END
        ALTER TABLE dbo.usuarios ADD DEFAULT 'Administrador' FOR rol;

        ALTER TABLE dbo.usuarios ADD CONSTRAINT CK_usuarios_rol
            CHECK (rol IN ('Administrador', 'RRHH', 'Consulta'));
    END
    """)
