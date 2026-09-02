import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import require_developer
from app.core.config import BACKUP_INTERVAL_SECONDS, DEFAULT_PAGE_SIZE, STATIC_DIR
from app.database.session import get_db
from app.services.backup_service import backup_path, create_backup, list_backups
from app.services.notification_service import publish_technical


logger = logging.getLogger(__name__)
router = APIRouter()
templates_env = Environment(
    loader=FileSystemLoader(str(STATIC_DIR.parent / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
)


@router.get('/system/backups', response_class=HTMLResponse)
def backups_page(request: Request, user=Depends(require_developer)):
    template = templates_env.get_template('system_backups.html')
    return HTMLResponse(template.render(active_page='system', user=user, csp_nonce=request.state.csp_nonce, default_page_size=DEFAULT_PAGE_SIZE))


@router.get('/api/system/backups')
def api_list_backups(_user=Depends(require_developer)):
    return {'items': list_backups()}


@router.post('/api/system/backups')
def api_create_backup(db: Session = Depends(get_db), _user=Depends(require_developer)):
    try:
        return create_backup(db)
    except (OSError, SQLAlchemyError, RuntimeError) as exc:
        db.rollback()
        try:
            publish_technical(db, 'Falla de backup', 'No se pudo crear la copia de seguridad. Revise los logs del sistema.')
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        logger.exception('No se pudo crear el backup manual.')
        raise HTTPException(status_code=503, detail='No se pudo crear la copia de seguridad.') from exc


@router.get('/api/system/backups/{filename}/download')
def api_download_backup(filename: str, _user=Depends(require_developer)):
    try:
        path = backup_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail='Copia de seguridad no encontrada.') from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail='Copia de seguridad no encontrada.')
    return FileResponse(path, media_type='application/octet-stream', filename=path.name)


def run_scheduled_backup() -> None:
    from app.database.session import SessionLocal

    db = SessionLocal()
    try:
        create_backup(db)
        logger.info('Copia de seguridad automática creada correctamente.')
    except Exception:
        db.rollback()
        try:
            publish_technical(db, 'Falla de backup automático', 'Falló la creación automática de la copia de seguridad. Revise los logs del sistema.')
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        logger.exception('Falló la copia de seguridad automática.')
    finally:
        db.close()


async def backup_loop() -> None:
    while True:
        await asyncio.to_thread(run_scheduled_backup)
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)