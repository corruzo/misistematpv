from datetime import timedelta

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.core.auth import ROLE_DEVELOPER, ROLE_HR, ROLE_INSPECTOR
from app.core.datetime_utils import utc_now
from app.models.notification import Notification
from app.models.alert_dismissal import AlertDismissal
from app.models.user import Usuario

PRIORITY_CRITICAL = 'critica'
PRIORITY_WARNING = 'advertencia'
PRIORITY_INFO = 'informativa'

ROLE_ACCESS_DENIED = (ROLE_HR, ROLE_DEVELOPER, ROLE_INSPECTOR)
ROLE_EXCEPTION_MARK = (ROLE_HR, ROLE_INSPECTOR)
ROLE_TECHNICAL = (ROLE_DEVELOPER,)
ROLE_ALL_USERS = (ROLE_HR, ROLE_DEVELOPER, ROLE_INSPECTOR)


def publish(db: Session, roles: tuple[str, ...], tipo: str, prioridad: str, titulo: str, mensaje: str) -> int:
    users = db.query(Usuario).filter(Usuario.rol.in_(roles), Usuario.activo == 1).all()
    for user in users:
        notification = Notification(usuario_id=user.id, tipo=tipo, prioridad=prioridad, titulo=titulo, mensaje=mensaje)
        db.add(notification)
    db.flush()
    return len(users)


def publish_access_denied(db: Session, employee_name: str, status: str) -> int:
    return publish(db, ROLE_ACCESS_DENIED, 'acceso_no_autorizado', PRIORITY_CRITICAL, 'Acceso no autorizado', f'{employee_name} intentó marcar con estado {status}. Detenga el acceso físico y gestione la incidencia.')


def publish_exception_mark(db: Session, employee_name: str, employee_id: int) -> int:
    return publish(db, ROLE_EXCEPTION_MARK, 'pase_temporal', PRIORITY_WARNING, 'Marcaje por excepción', f'{employee_name} realizó un marcaje manual sin carnet RFID (empleado {employee_id}). Dé seguimiento a la entrega de la ficha.')


def publish_technical(db: Session, titulo: str, mensaje: str) -> int:
    return publish(db, ROLE_TECHNICAL, 'incidencia_tecnica', PRIORITY_CRITICAL, titulo, mensaje)


def _actor_name(db: Session, usuario_id: int | None) -> str:
    if usuario_id is None:
        return 'Sistema'
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    return user.nombre if user and getattr(user, 'nombre', None) else f'Usuario {usuario_id}'


def publish_employee_registered(db: Session, employee, usuario_id: int | None) -> int:
    actor = _actor_name(db, usuario_id)
    return publish(db, ROLE_ALL_USERS, 'empleado_registrado', PRIORITY_INFO, 'Nuevo empleado registrado', f'{actor} registró al empleado {employee.nombre_apellido} (cédula {employee.cedula}).')


def publish_employee_updated(db: Session, employee_name: str, usuario_id: int | None) -> int:
    actor = _actor_name(db, usuario_id)
    return publish(db, ROLE_ALL_USERS, 'empleado_registrado', PRIORITY_INFO, 'Empleado actualizado', f'{actor} actualizó los datos del empleado {employee_name}.')


def publish_employee_status_changed(db: Session, employee_name: str, old_status: str, new_status: str, usuario_id: int | None) -> int:
    actor = _actor_name(db, usuario_id)
    return publish(db, ROLE_ALL_USERS, 'empleado_estado_cambiado', PRIORITY_WARNING, 'Cambio de estatus de empleado', f'{actor} cambió el estatus de {employee_name} de {old_status} a {new_status}.')


def publish_organization_changed(db: Session, detail: str, usuario_id: int | None) -> int:
    actor = _actor_name(db, usuario_id)
    return publish(db, ROLE_ALL_USERS, 'organizacion_cambiada', PRIORITY_INFO, 'Estructura organizacional actualizada', f'{actor}: {detail}')


def publish_user_changed(db: Session, username: str, action: str, usuario_id: int | None) -> int:
    actor = _actor_name(db, usuario_id)
    return publish(db, ROLE_ALL_USERS, 'usuario_cambiado', PRIORITY_INFO, 'Usuario del sistema actualizado', f'{actor} {action} al usuario {username}.')


def publish_attendance_corrected(db: Session, employee_name: str, old_type: str, new_type: str, reason: str, usuario_id: int) -> int:
    actor = _actor_name(db, usuario_id)
    return publish(db, ROLE_ALL_USERS, 'marcaje_corregido', PRIORITY_WARNING, 'Marcaje corregido', f'{actor} corrigió el marcaje de {employee_name}: {old_type} a {new_type}. Motivo: {reason}')


def publish_reader_status_changed(db: Session, garita_name: str, connected: bool) -> int:
    status = 'conectado' if connected else 'desconectado'
    priority = PRIORITY_INFO if connected else PRIORITY_CRITICAL
    return publish(db, ROLE_ALL_USERS, 'lector_estado_cambiado', priority, f'Lector RFID {status}', f'El lector RFID de {garita_name} ahora está {status}.')


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
    return changed


def discard(db: Session, user_id: int, notification_id: int) -> bool:
    changed = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.usuario_id == user_id,
        Notification.descartada_en.is_(None),
    ).update({Notification.descartada_en: utc_now()}, synchronize_session=False)
    db.commit()
    return bool(changed)


def cleanup_temporary_data(db: Session, retention_days: int = 30) -> dict[str, int]:
    cutoff = utc_now() - timedelta(days=retention_days)
    deleted_notifications = db.query(Notification).filter(
        Notification.creada_en < cutoff,
        or_(Notification.descartada_en.isnot(None), Notification.leida_en.isnot(None)),
    ).delete(synchronize_session=False)
    deleted_alert_dismissals = db.query(AlertDismissal).filter(
        AlertDismissal.descartada_en < cutoff,
    ).delete(synchronize_session=False)
    db.commit()
    return {'notifications': deleted_notifications, 'alert_dismissals': deleted_alert_dismissals}


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