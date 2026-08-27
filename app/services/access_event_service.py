import logging
from datetime import date, datetime, time

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.access_event import AccessDeniedEvent
from app.services.attendance_service import EmployeeAccessDeniedError
from app.services.notification_service import publish_access_denied
from app.core.datetime_utils import LOCAL_TIMEZONE, as_utc, to_local

logger = logging.getLogger(__name__)


def record_denied_event(db: Session, error: EmployeeAccessDeniedError) -> bool:
    event = AccessDeniedEvent(
        empleado_id=error.employee_id,
        empleado_nombre=error.employee_name,
        estado=error.employee_status,
        fecha_hora=error.marked_at or as_utc(datetime.now(LOCAL_TIMEZONE)),
    )
    try:
        db.add(event)
        publish_access_denied(db, error.employee_name, error.employee_status)
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        logger.exception('No se pudo persistir la alerta de acceso denegado.')
        return False


def get_denied_events(db: Session, after_id: int = 0, limit: int = 50) -> list[dict]:
    events = (
        db.query(AccessDeniedEvent)
        .filter(AccessDeniedEvent.id > after_id)
        .order_by(AccessDeniedEvent.id.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            'id': event.id,
            'code': 'employee_access_denied',
            'detail': 'El empleado no está activo.',
            'empleado_nombre': event.empleado_nombre,
            'estado': event.estado,
            'fecha_hora': to_local(event.fecha_hora).isoformat(),
        }
        for event in events
    ]


def list_denied_events(db: Session, date_from: date | None = None, date_to: date | None = None, limit: int = 100) -> list[dict]:
    start_date = date_from or datetime.now(LOCAL_TIMEZONE).date()
    end_date = date_to or start_date
    start = as_utc(datetime.combine(start_date, time.min, LOCAL_TIMEZONE))
    end = as_utc(datetime.combine(end_date, time.max, LOCAL_TIMEZONE))
    events = (
        db.query(AccessDeniedEvent)
        .filter(AccessDeniedEvent.fecha_hora >= start, AccessDeniedEvent.fecha_hora <= end)
        .order_by(AccessDeniedEvent.fecha_hora.desc(), AccessDeniedEvent.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'id': event.id,
            'empleado_nombre': event.empleado_nombre,
            'estado': event.estado,
            'fecha_hora': to_local(event.fecha_hora).isoformat(),
            'detalle': 'Intento de marcaje bloqueado',
        }
        for event in events
    ]
