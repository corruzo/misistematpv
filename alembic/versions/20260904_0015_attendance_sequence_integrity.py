"""Protect attendance alternation at the database boundary.

Revision ID: 20260904_0015
Revises: 20260827_0014
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260904_0015'
down_revision: Union[str, None] = '20260827_0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TRIGGER = 'TR_marcajes_asistencia_validate_sequence'


def upgrade() -> None:
    trigger_sql = f"""
    CREATE TRIGGER dbo.{_TRIGGER}
    ON dbo.marcajes_asistencia
    AFTER INSERT, UPDATE
    AS
    BEGIN
        SET NOCOUNT ON;

        IF EXISTS (
            SELECT 1
            FROM (
            SELECT
                current_row.tipo,
                LAG(current_row.tipo) OVER (
                    PARTITION BY current_row.empleado_id
                    ORDER BY current_row.fecha_hora, current_row.id
                ) AS previous_type
            FROM dbo.marcajes_asistencia current_row WITH (UPDLOCK, HOLDLOCK)
            WHERE current_row.empleado_id IN (SELECT empleado_id FROM inserted)
            ) ordered_records
            WHERE ordered_records.tipo = ordered_records.previous_type
        )
        BEGIN
            THROW 51001, 'La secuencia de asistencia debe alternar ENTRADA y SALIDA.', 1;
        END;
    END
    """.replace("'", "''")
    op.execute(f"""
    IF OBJECT_ID('dbo.{_TRIGGER}', 'TR') IS NOT NULL
        DROP TRIGGER dbo.{_TRIGGER};
    EXEC(N'{trigger_sql}');
    """)


def downgrade() -> None:
    op.execute(f"""
    IF OBJECT_ID('dbo.{_TRIGGER}', 'TR') IS NOT NULL
        DROP TRIGGER dbo.{_TRIGGER};
    """)
