import json
from datetime import date, datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.models.audit import AuditRecord


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)


def snapshot(values: dict | None) -> str | None:
    return json.dumps(values, ensure_ascii=True, default=_json_default) if values is not None else None


def add_audit(db: Session, usuario_id: int | None, accion: str, entidad: str, entidad_id: int | None,
              antes: dict | None = None, despues: dict | None = None) -> AuditRecord:
    record = AuditRecord(
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        datos_antes=snapshot(antes),
        datos_despues=snapshot(despues),
    )
    db.add(record)
    return record