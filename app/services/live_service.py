import asyncio
import json
from collections.abc import AsyncIterator

from sqlalchemy import func

from app.database.session import SessionLocal
from app.models.attendance import AttendanceRecord
from app.models.access_event import AccessDeniedEvent
from app.models.notification import Notification
from app.schemas.attendance import AttendanceOrigin
from app.services.access_event_service import get_denied_events
from app.services.attendance_service import get_attendance_since
from app.services.live_bus import current_live_version, wait_for_live_change


def _event(event_type: str, payload) -> str:
    data = json.dumps(payload, ensure_ascii=True, default=str)
    return f'event: {event_type}\ndata: {data}\n\n'


def _last_ids(db, user_id: int) -> tuple[int, int, int]:
    attendance_id = db.query(func.max(AttendanceRecord.id)).scalar() or 0
    denied_id = db.query(func.max(AccessDeniedEvent.id)).scalar() or 0
    notification_id = db.query(func.max(Notification.id)).filter(Notification.usuario_id == user_id).scalar() or 0
    return attendance_id, denied_id, notification_id


async def stream_events(user_id: int) -> AsyncIterator[str]:
    db = SessionLocal()
    try:
        attendance_id, denied_id, notification_id = _last_ids(db, user_id)
    finally:
        db.close()

    live_version = current_live_version()
    yield ': connected\n\n'
    while True:
        live_version = await asyncio.to_thread(wait_for_live_change, live_version, 25)
        db = SessionLocal()
        try:
            from app.services.notification_service import list_notifications

            records = get_attendance_since(db, attendance_id, AttendanceOrigin.PUERTO_COM)
            denied = get_denied_events(db, denied_id)
            notifications, _unread = list_notifications(db, user_id, notification_id)
            if records:
                attendance_id = max(attendance_id, *(item.id for item in records))
                for item in records:
                    yield _event('attendance', item.model_dump(mode='json'))
            if denied:
                denied_id = max(denied_id, *(item.get('id', 0) for item in denied))
                for item in denied:
                    yield _event('access_denied', item)
            if notifications:
                notification_id = max(notification_id, *(item['id'] for item in notifications))
                for item in notifications:
                    yield _event('notification', item)
        finally:
            db.close()
        await asyncio.sleep(1)