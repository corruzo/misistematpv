import hashlib
import json
from datetime import date, datetime, timezone
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


def audit_digest(record: AuditRecord) -> str:
    fecha = record.fecha if isinstance(record.fecha, datetime) else None
    fecha_text = ''
    if fecha is not None:
        fecha_text = (fecha.astimezone(timezone.utc) if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)).isoformat()
        if '.' in fecha_text:
            head, tail = fecha_text.split('.', 1)
            fraction, offset = tail.split('+', 1)
            fecha_text = f'{head}.{fraction[:6].ljust(6, "0")}+{offset}'
    payload = '|'.join([
        str(record.id),
        str(record.usuario_id or 0),
        str(record.accion or ''),
        str(record.entidad or ''),
        str(record.entidad_id or 0),
        str(record.datos_antes or ''),
        str(record.datos_despues or ''),
        fecha_text,
        str(record.hash_anterior or '').rstrip(),
    ])
    return hashlib.sha256(payload.encode('utf-16le')).hexdigest().upper()


def add_audit(db: Session, usuario_id: int | None, accion: str, entidad: str, entidad_id: int | None,
              antes: dict | None = None, despues: dict | None = None) -> AuditRecord:
    previous_row = db.query(AuditRecord.hash_registro).order_by(AuditRecord.id.desc()).first()
    try:
        previous_hash = previous_row[0] if previous_row else None
    except (TypeError, KeyError):
        previous_hash = getattr(previous_row, 'hash_registro', None)
    record = AuditRecord(
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        datos_antes=snapshot(antes),
        datos_despues=snapshot(despues),
        fecha=datetime.now(timezone.utc),
        hash_anterior=previous_hash,
    )
    db.add(record)
    db.flush()
    record.hash_registro = audit_digest(record)
    return record


def verify_audit_chain(db: Session) -> bool:
    records = db.query(AuditRecord).order_by(AuditRecord.id.asc()).all()
    previous_hash = None
    for record in records:
        stored_previous = (record.hash_anterior or '').rstrip() or None
        stored_hash = (record.hash_registro or '').rstrip().upper() or None
        if stored_previous != previous_hash or stored_hash != audit_digest(record):
            return False
        previous_hash = stored_hash
    return True


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