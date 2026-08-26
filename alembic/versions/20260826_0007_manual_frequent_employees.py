"""Add per-user manual attendance frequent employees.

Revision ID: 20260826_0007
Revises: 20260825_0006
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260826_0007'
down_revision: Union[str, None] = '20260825_0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.empleados_frecuentes_manual', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.empleados_frecuentes_manual (
            id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_empleados_frecuentes_manual PRIMARY KEY,
            usuario_id INT NOT NULL,
            empleado_id INT NOT NULL,
            posicion INT NOT NULL CONSTRAINT DF_empleados_frecuentes_manual_posicion DEFAULT 0,
            CONSTRAINT FK_empleados_frecuentes_manual_usuario FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id),
            CONSTRAINT FK_empleados_frecuentes_manual_empleado FOREIGN KEY (empleado_id) REFERENCES dbo.empleados(id),
            CONSTRAINT UQ_empleados_frecuentes_manual_usuario_empleado UNIQUE (usuario_id, empleado_id)
        );
        CREATE INDEX IX_empleados_frecuentes_manual_usuario_posicion
            ON dbo.empleados_frecuentes_manual(usuario_id, posicion, id);
    END
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.empleados_frecuentes_manual', 'U') IS NOT NULL
        DROP TABLE dbo.empleados_frecuentes_manual;
    """)