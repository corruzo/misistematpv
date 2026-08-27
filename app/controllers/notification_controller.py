import asyncio

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.database.session import SessionLocal, get_db
from app.models.access_event import AccessDeniedEvent
from app.models.attendance import AttendanceRecord
from app.models.notification import Notification
from app.models.user import Usuario
from app.schemas.attendance import AttendanceOrigin
from app.services.access_event_service import get_denied_events
from app.services.attendance_service import get_attendance_since
from app.services.notification_service import count_unread, discard, list_notifications, mark_read
from app.services.auth_service import SESSION_COOKIE, get_user_by_token

router = APIRouter()


@router.websocket('/api/ws')
async def websocket_events(websocket: WebSocket):
    token = websocket.cookies.get(SESSION_COOKIE)
    with SessionLocal() as db:
        user = get_user_by_token(db, token)
        user_id = user.id if user else None
    if user_id is None:
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    try:
        attendance_id = db.query(func.max(AttendanceRecord.id)).scalar() or 0
        denied_id = db.query(func.max(AccessDeniedEvent.id)).scalar() or 0
        notification_id = db.query(func.max(Notification.id)).filter(Notification.usuario_id == user_id).scalar() or 0
    finally:
        db.close()
    try:
        while True:
            await asyncio.sleep(1)
            db = SessionLocal()
            try:
                records = get_attendance_since(db, attendance_id, AttendanceOrigin.PUERTO_COM)
                denied = get_denied_events(db, denied_id)
                notifications, _unread = list_notifications(db, user_id, notification_id)
                if records:
                    attendance_id = max(attendance_id, *(item.id for item in records))
                    for item in records:
                        await websocket.send_json({'type': 'attendance', 'payload': item.model_dump(mode='json')})
                if denied:
                    denied_id = max(denied_id, *(item.get('id', 0) for item in denied))
                    for item in denied:
                        await websocket.send_json({'type': 'access_denied', 'payload': item})
                if notifications:
                    notification_id = max(notification_id, *(item['id'] for item in notifications))
                    for item in notifications:
                        await websocket.send_json({'type': 'notification', 'payload': item})
                        if item['tipo'] in {'empleado_registrado', 'empleado_estado_cambiado'}:
                            await websocket.send_json({'type': 'employee_changed', 'payload': {}})
                        elif item['tipo'] == 'marcaje_corregido':
                            await websocket.send_json({'type': 'attendance', 'payload': {'refresh': True}})
                        elif item['tipo'] == 'lector_estado_cambiado':
                            await websocket.send_json({'type': 'reader_changed', 'payload': {}})
            finally:
                db.close()
    except WebSocketDisconnect:
        pass
@router.get('/api/notifications')
def notifications(
    after_id: int = Query(0, ge=0),
    db: Session = Depends(get_db), user: Usuario = Depends(require_user),
):
    items, unread = list_notifications(db, user.id, after_id)
    return {'items': items, 'unread': unread}


@router.patch('/api/notifications/read')
def read_notifications(
    notification_id: int | None = Query(None, gt=0),
    db: Session = Depends(get_db), user: Usuario = Depends(require_user),
):
    mark_read(db, user.id, notification_id)
    return {'ok': True, 'unread': count_unread(db, user.id)}


@router.delete('/api/notifications/{notification_id}')
def delete_notification(notification_id: int, db: Session = Depends(get_db), user: Usuario = Depends(require_user)):
    if not discard(db, user.id, notification_id):
        return {'ok': True}
    return {'ok': True, 'unread': count_unread(db, user.id)}