"""Rebuild audit hashes using the application canonical representation.

Revision ID: 20260904_0017
Revises: 20260904_0016
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260904_0017'
down_revision: Union[str, None] = '20260904_0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.TR_auditoria_immutable_update', 'TR') IS NOT NULL DROP TRIGGER dbo.TR_auditoria_immutable_update;
    IF OBJECT_ID('dbo.TR_auditoria_immutable_delete', 'TR') IS NOT NULL DROP TRIGGER dbo.TR_auditoria_immutable_delete;
    """)
    op.execute("""
    DECLARE @previous CHAR(64) = NULL;
    DECLARE @id INT;
    DECLARE @fecha DATETIME2;
    DECLARE @hash CHAR(64);
    DECLARE audit_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT id FROM dbo.auditoria ORDER BY id;
    OPEN audit_cursor;
    FETCH NEXT FROM audit_cursor INTO @id;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SELECT @fecha = fecha FROM dbo.auditoria WHERE id = @id;
        SELECT @hash = CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT(
            id, '|', ISNULL(usuario_id, ''), '|', accion, '|', entidad, '|',
            ISNULL(entidad_id, ''), '|', ISNULL(datos_antes, ''), '|',
            ISNULL(datos_despues, ''), '|', CONVERT(NVARCHAR(40), SWITCHOFFSET(CONVERT(DATETIMEOFFSET, @fecha), '+00:00'), 127), '|',
            ISNULL(@previous, '')
        )), 2)
        FROM dbo.auditoria WHERE id = @id;
        UPDATE dbo.auditoria SET hash_anterior = @previous, hash_registro = @hash WHERE id = @id;
        SET @previous = @hash;
        FETCH NEXT FROM audit_cursor INTO @id;
    END
    CLOSE audit_cursor;
    DEALLOCATE audit_cursor;
    """)
    update_sql = """
    CREATE TRIGGER dbo.TR_auditoria_immutable_update
    ON dbo.auditoria
    INSTEAD OF UPDATE
    AS
    BEGIN
        THROW 51002, 'La bitacora de auditoria es inmutable.', 1;
    END
    """.replace("'", "''")
    delete_sql = """
    CREATE TRIGGER dbo.TR_auditoria_immutable_delete
    ON dbo.auditoria
    INSTEAD OF DELETE
    AS
    BEGIN
        THROW 51003, 'La bitacora de auditoria es inmutable.', 1;
    END
    """.replace("'", "''")
    op.execute(f"EXEC(N'{update_sql}');")
    op.execute(f"EXEC(N'{delete_sql}');")


def downgrade() -> None:
    pass
