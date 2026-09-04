"""Rebuild audit hashes with the exact application canonicalization.

Revision ID: 20260904_0023
Revises: 20260904_0022
"""
import hashlib
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '20260904_0023'
down_revision: Union[str, None] = '20260904_0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def _digest(row, previous: str | None) -> str:
    fecha = row.fecha
    if fecha.tzinfo:
        fecha = fecha.astimezone(timezone.utc)
    else:
        fecha = fecha.replace(tzinfo=timezone.utc)
    fecha_text = fecha.isoformat()
    if '.' in fecha_text:
        head, tail = fecha_text.split('.', 1)
        fraction, offset = tail.split('+', 1)
        fecha_text = f'{head}.{fraction[:6].ljust(6, "0")}+{offset}'
    payload = '|'.join([
        str(row.id), str(row.usuario_id or 0), str(row.accion or ''),
        str(row.entidad or ''), str(row.entidad_id or 0),
        str(row.datos_antes or ''), str(row.datos_despues or ''), fecha_text,
        str(previous or '').rstrip(),
    ])
    return hashlib.sha256(payload.encode('utf-16le')).hexdigest().upper()


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("""
        IF OBJECT_ID('dbo.TR_auditoria_immutable_update', 'TR') IS NOT NULL DROP TRIGGER dbo.TR_auditoria_immutable_update;
        IF OBJECT_ID('dbo.TR_auditoria_immutable_delete', 'TR') IS NOT NULL DROP TRIGGER dbo.TR_auditoria_immutable_delete;
    """))
    rows = bind.execute(text("""
        SELECT id, usuario_id, accion, entidad, entidad_id, datos_antes, datos_despues, fecha
        FROM dbo.auditoria ORDER BY id
    """)).fetchall()
    previous = None
    for row in rows:
        digest = _digest(row, previous)
        bind.execute(text("""
            UPDATE dbo.auditoria
            SET hash_anterior = :previous, hash_registro = :digest
            WHERE id = :id
        """), {'previous': previous, 'digest': digest, 'id': row.id})
        previous = digest
    bind.execute(text("""
        CREATE TRIGGER dbo.TR_auditoria_immutable_update ON dbo.auditoria INSTEAD OF UPDATE AS
        BEGIN THROW 51002, 'La bitacora de auditoria es inmutable.', 1; END
    """))
    bind.execute(text("""
        CREATE TRIGGER dbo.TR_auditoria_immutable_delete ON dbo.auditoria INSTEAD OF DELETE AS
        BEGIN THROW 51003, 'La bitacora de auditoria es inmutable.', 1; END
    """))


def downgrade() -> None:
    pass
