"""Add indexes supporting bounded list and attendance queries.

Revision ID: 20260824_0004
Revises: 20260821_0003
"""
from typing import Sequence, Union

from alembic import op

revision: str = '20260824_0004'
down_revision: Union[str, None] = '20260821_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.marcajes_asistencia', 'U') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_marcajes_empleado_fecha_id' AND object_id = OBJECT_ID('dbo.marcajes_asistencia'))
        CREATE INDEX IX_marcajes_empleado_fecha_id ON dbo.marcajes_asistencia(empleado_id, fecha_hora DESC, id DESC);

    IF OBJECT_ID('dbo.empleados', 'U') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_empleados_fecha_creacion_id' AND object_id = OBJECT_ID('dbo.empleados'))
        CREATE INDEX IX_empleados_fecha_creacion_id ON dbo.empleados(fecha_creacion DESC, id DESC);

    IF OBJECT_ID('dbo.usuarios', 'U') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_usuarios_nombre_username' AND object_id = OBJECT_ID('dbo.usuarios'))
        CREATE INDEX IX_usuarios_nombre_username ON dbo.usuarios(nombre ASC, username ASC);

    IF OBJECT_ID('dbo.departamentos', 'U') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_departamentos_gerencia_id' AND object_id = OBJECT_ID('dbo.departamentos'))
        CREATE INDEX IX_departamentos_gerencia_id ON dbo.departamentos(gerencia_id, estado, nombre);

    IF OBJECT_ID('dbo.cargos', 'U') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_cargos_departamento_id' AND object_id = OBJECT_ID('dbo.cargos'))
        CREATE INDEX IX_cargos_departamento_id ON dbo.cargos(departamento_id, estado, nombre);
    """)


def downgrade() -> None:
    op.execute("""
    IF OBJECT_ID('dbo.marcajes_asistencia', 'U') IS NOT NULL AND EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_marcajes_empleado_fecha_id' AND object_id = OBJECT_ID('dbo.marcajes_asistencia'))
        DROP INDEX IX_marcajes_empleado_fecha_id ON dbo.marcajes_asistencia;
    IF OBJECT_ID('dbo.empleados', 'U') IS NOT NULL AND EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_empleados_fecha_creacion_id' AND object_id = OBJECT_ID('dbo.empleados'))
        DROP INDEX IX_empleados_fecha_creacion_id ON dbo.empleados;
    IF OBJECT_ID('dbo.usuarios', 'U') IS NOT NULL AND EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_usuarios_nombre_username' AND object_id = OBJECT_ID('dbo.usuarios'))
        DROP INDEX IX_usuarios_nombre_username ON dbo.usuarios;
    IF OBJECT_ID('dbo.departamentos', 'U') IS NOT NULL AND EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_departamentos_gerencia_id' AND object_id = OBJECT_ID('dbo.departamentos'))
        DROP INDEX IX_departamentos_gerencia_id ON dbo.departamentos;
    IF OBJECT_ID('dbo.cargos', 'U') IS NOT NULL AND EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_cargos_departamento_id' AND object_id = OBJECT_ID('dbo.cargos'))
        DROP INDEX IX_cargos_departamento_id ON dbo.cargos;
    """)
