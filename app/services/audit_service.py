import json
from datetime import date, datetime
from enum import Enum

from sqlalchemy import func
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


def list_audit_events(db: Session, *, entidad: str | None = None, since: datetime | None = None, limit: int = 50) -> list[AuditRecord]:
    query = db.query(AuditRecord)
    if entidad is not None:
        query = query.filter(AuditRecord.entidad == entidad)
    if since is not None:
        query = query.filter(AuditRecord.fecha >= since)
    return query.order_by(AuditRecord.fecha.desc(), AuditRecord.id.desc()).limit(limit).all()


def summarize_audit(db: Session, *, since: datetime | None = None) -> dict[str, int | list[dict]]:
    query = db.query(AuditRecord)
    if since is not None:
        query = query.filter(AuditRecord.fecha >= since)
    by_entity = query.with_entities(AuditRecord.entidad, func.count(AuditRecord.id)).group_by(AuditRecord.entidad).all()
    return {
        'total': query.count(),
        'by_entity': {entity: count for entity, count in by_entity},
    }