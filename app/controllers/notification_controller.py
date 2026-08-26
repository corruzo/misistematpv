from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import require_user
from app.database.session import get_db
from app.models.user import Usuario
from app.services.notification_service import count_unread, discard, list_notifications, mark_read
from app.services.live_service import stream_events

router = APIRouter()


@router.get('/api/live')
async def live_events(user: Usuario = Depends(require_user)):
    return StreamingResponse(
        stream_events(user.id),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'},
    )


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