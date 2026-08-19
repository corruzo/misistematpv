from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.core.auth import require_admin, require_page_user, require_user
from app.core.config import APP_ENV, STATIC_DIR
from app.database.session import get_db
from app.schemas.attendance import AttendanceManualRequest, AttendanceOrigin, AttendanceScanRequest
from app.services.attendance_service import AttendanceError, attendance_summary, list_attendance, register_manual, register_scan
from app.services.organization_service import get_organization_tree
from app.services.card_reader import SimulatedCardReader


router = APIRouter()
templates_env = Environment(
    loader=FileSystemLoader(str(STATIC_DIR.parent / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
)


@router.get('/attendance', response_class=HTMLResponse)
def attendance_page(user=Depends(require_page_user)):
    template = templates_env.get_template('attendance.html')
    return HTMLResponse(template.render(active_page='attendance', user=user))


@router.get('/attendance/history', response_class=HTMLResponse)
def attendance_history_page(user=Depends(require_page_user)):
    template = templates_env.get_template('attendance_history.html')
    return HTMLResponse(template.render(active_page='attendance_history', user=user))


@router.get('/attendance/summary', response_class=HTMLResponse)
def attendance_summary_page(user=Depends(require_page_user)):
    template = templates_env.get_template('attendance_summary.html')
    return HTMLResponse(template.render(active_page='attendance_summary', user=user))


@router.post('/api/attendance/simulate-scan')
def simulate_scan(payload: AttendanceScanRequest, db: Session = Depends(get_db), _user=Depends(require_user)):
    if APP_ENV != 'development':
        raise HTTPException(status_code=404, detail='Recurso no disponible.')
    try:
        reader = SimulatedCardReader(payload.codigo_tarjeta)
        return register_scan(db, reader.read_card_code(), AttendanceOrigin.SIMULADOR_DEV)
    except AttendanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post('/api/attendance/manual-mark')
def manual_mark(payload: AttendanceManualRequest, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    try:
        return register_manual(db, payload.empleado_id)
    except AttendanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get('/api/attendance/history')
def attendance_history(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    date_from: date | None = None, date_to: date | None = None,
    empleado_q: str | None = Query(None, max_length=150),
    departamento_ids: list[int] | None = Query(None), gerencia_ids: list[int] | None = Query(None),
    db: Session = Depends(get_db), _user=Depends(require_user),
):
    return list_attendance(db, page, page_size, date_from, date_to, empleado_q, departamento_ids, gerencia_ids)


@router.get('/api/attendance/summary')
def attendance_summary_route(db: Session = Depends(get_db), _user=Depends(require_user)):
    return attendance_summary(db)


@router.get('/api/attendance/filter-options')
def attendance_filter_options(db: Session = Depends(get_db), _user=Depends(require_user)):
    tree = get_organization_tree(db)
    gerencias = [{'id': item['id'], 'nombre': item['nombre']} for item in tree]
    departamentos = [
        {'id': department['id'], 'nombre': department['nombre'], 'gerencia_id': item['id']}
        for item in tree for department in item.get('departamentos', [])
    ]
    return {'gerencias': gerencias, 'departamentos': departamentos}