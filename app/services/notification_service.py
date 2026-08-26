from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.auth import ROLE_DEVELOPER, ROLE_HR, ROLE_INSPECTOR
from app.core.datetime_utils import utc_now
from app.models.notification import Notification
from app.models.user import Usuario
from app.services.live_bus import notify_live_change

PRIORITY_CRITICAL = 'critica'
PRIORITY_WARNING = 'advertencia'
PRIORITY_INFO = 'informativa'

ROLE_ACCESS_DENIED = (ROLE_HR, ROLE_DEVELOPER, ROLE_INSPECTOR)
ROLE_EXCEPTION_MARK = (ROLE_HR, ROLE_INSPECTOR)
ROLE_TECHNICAL = (ROLE_DEVELOPER,)


def publish(db: Session, roles: tuple[str, ...], tipo: str, prioridad: str, titulo: str, mensaje: str) -> int:
    users = db.query(Usuario).filter(Usuario.rol.in_(roles), Usuario.activo == 1).all()
    for user in users:
        db.add(Notification(usuario_id=user.id, tipo=tipo, prioridad=prioridad, titulo=titulo, mensaje=mensaje))
    db.flush()
    return len(users)


def publish_access_denied(db: Session, employee_name: str, status: str) -> int:
    return publish(db, ROLE_ACCESS_DENIED, 'acceso_no_autorizado', PRIORITY_CRITICAL, 'Acceso no autorizado', f'{employee_name} intentó marcar con estado {status}. Detenga el acceso físico y gestione la incidencia.')


def publish_exception_mark(db: Session, employee_name: str, employee_id: int) -> int:
    return publish(db, ROLE_EXCEPTION_MARK, 'pase_temporal', PRIORITY_WARNING, 'Marcaje por excepción', f'{employee_name} realizó un marcaje manual sin carnet RFID (empleado {employee_id}). Dé seguimiento a la entrega de la ficha.')


def publish_technical(db: Session, titulo: str, mensaje: str) -> int:
    return publish(db, ROLE_TECHNICAL, 'incidencia_tecnica', PRIORITY_CRITICAL, titulo, mensaje)


def list_notifications(db: Session, user_id: int, after_id: int = 0, limit: int = 50) -> tuple[list[dict], int | None]:
    unread_window = func.sum(case((Notification.leida_en.is_(None), 1), else_=0)).over()
    query = db.query(Notification, unread_window.label('unread_count')).filter(
        Notification.usuario_id == user_id,
        Notification.descartada_en.is_(None),
    )
    if after_id:
        query = query.filter(Notification.id > after_id)
    rows = query.order_by(Notification.id.asc()).limit(limit).all()
    unread = int(rows[0][1] or 0) if rows and not after_id else None
    return [_serialize(row[0]) for row in rows], unread


def count_unread(db: Session, user_id: int) -> int:
    return db.query(Notification).filter(
        Notification.usuario_id == user_id,
        Notification.leida_en.is_(None),
        Notification.descartada_en.is_(None),
    ).count()


def mark_read(db: Session, user_id: int, notification_id: int | None = None) -> int:
    query = db.query(Notification).filter(Notification.usuario_id == user_id, Notification.descartada_en.is_(None))
    if notification_id is not None:
        query = query.filter(Notification.id == notification_id)
    changed = query.update({Notification.leida_en: utc_now()}, synchronize_session=False)
    db.commit()
    notify_live_change()
    return changed


def discard(db: Session, user_id: int, notification_id: int) -> bool:
    changed = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.usuario_id == user_id,
        Notification.descartada_en.is_(None),
    ).update({Notification.descartada_en: utc_now()}, synchronize_session=False)
    db.commit()
    notify_live_change()
    return bool(changed)


def _serialize(row: Notification) -> dict:
    return {
        'id': row.id,
        'tipo': row.tipo,
        'prioridad': row.prioridad,
        'titulo': row.titulo,
        'mensaje': row.mensaje,
        'creada_en': row.creada_en.isoformat() if row.creada_en else None,
        'leida': row.leida_en is not None,
    }