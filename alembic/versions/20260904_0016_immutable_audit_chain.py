"""Add an immutable chained audit ledger.

Revision ID: 20260904_0016
Revises: 20260904_0015
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260904_0016'
down_revision: Union[str, None] = '20260904_0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRIGGER_UPDATE = 'TR_auditoria_immutable_update'
_TRIGGER_DELETE = 'TR_auditoria_immutable_delete'


def upgrade() -> None:
    op.execute("""
    IF COL_LENGTH('dbo.auditoria', 'hash_anterior') IS NULL
        ALTER TABLE dbo.auditoria ADD hash_anterior CHAR(64) NULL;
    IF COL_LENGTH('dbo.auditoria', 'hash_registro') IS NULL
        ALTER TABLE dbo.auditoria ADD hash_registro CHAR(64) NULL;
    """)
    op.execute("""
    DECLARE @previous CHAR(64) = NULL;
    DECLARE @id INT;
    DECLARE audit_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT id FROM dbo.auditoria ORDER BY id;
    OPEN audit_cursor;
    FETCH NEXT FROM audit_cursor INTO @id;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        UPDATE dbo.auditoria
        SET hash_anterior = @previous,
            hash_registro = CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT(
                id, '|', ISNULL(usuario_id, ''), '|', accion, '|', entidad, '|',
                ISNULL(entidad_id, ''), '|', ISNULL(datos_antes, ''), '|',
                ISNULL(datos_despues, ''), '|', CONVERT(NVARCHAR(40), fecha, 127), '|',
                ISNULL(@previous, '')
            )), 2)
        WHERE id = @id;
        SELECT @previous = hash_registro FROM dbo.auditoria WHERE id = @id;
        FETCH NEXT FROM audit_cursor INTO @id;
    END
    CLOSE audit_cursor;
    DEALLOCATE audit_cursor;
    """)
    op.execute("""
    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = 'UX_auditoria_hash_registro'
          AND object_id = OBJECT_ID('dbo.auditoria')
    )
        CREATE UNIQUE INDEX UX_auditoria_hash_registro ON dbo.auditoria(hash_registro) WHERE hash_registro IS NOT NULL;
    """)
    op.execute(f"IF OBJECT_ID('dbo.{_TRIGGER_UPDATE}', 'TR') IS NOT NULL DROP TRIGGER dbo.{_TRIGGER_UPDATE};")
    update_sql = f"""
    CREATE TRIGGER dbo.{_TRIGGER_UPDATE}
    ON dbo.auditoria
    INSTEAD OF UPDATE
    AS
    BEGIN
        THROW 51002, 'La bitacora de auditoria es inmutable.', 1;
    END
    """.replace("'", "''")
    op.execute(f"EXEC(N'{update_sql}');")
    op.execute(f"IF OBJECT_ID('dbo.{_TRIGGER_DELETE}', 'TR') IS NOT NULL DROP TRIGGER dbo.{_TRIGGER_DELETE};")
    delete_sql = f"""
    CREATE TRIGGER dbo.{_TRIGGER_DELETE}
    ON dbo.auditoria
    INSTEAD OF DELETE
    AS
    BEGIN
        THROW 51003, 'La bitacora de auditoria es inmutable.', 1;
    END
    """.replace("'", "''")
    op.execute(f"EXEC(N'{delete_sql}');")


def downgrade() -> None:
    op.execute(f"""
    IF OBJECT_ID('dbo.{_TRIGGER_UPDATE}', 'TR') IS NOT NULL DROP TRIGGER dbo.{_TRIGGER_UPDATE};
    IF OBJECT_ID('dbo.{_TRIGGER_DELETE}', 'TR') IS NOT NULL DROP TRIGGER dbo.{_TRIGGER_DELETE};
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_auditoria_hash_registro' AND object_id = OBJECT_ID('dbo.auditoria'))
        DROP INDEX UX_auditoria_hash_registro ON dbo.auditoria;
    IF COL_LENGTH('dbo.auditoria', 'hash_anterior') IS NOT NULL ALTER TABLE dbo.auditoria DROP COLUMN hash_anterior;
    IF COL_LENGTH('dbo.auditoria', 'hash_registro') IS NOT NULL ALTER TABLE dbo.auditoria DROP COLUMN hash_registro;
    """)
