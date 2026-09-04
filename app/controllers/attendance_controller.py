import csv
from datetime import date, datetime
from io import StringIO
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import PERMISSION_ACCESS_KIOSK, require_employee_manager, require_manual_attendance, require_page_user, require_permission, require_read_access, require_user
from app.core.config import APP_ENV, ATTENDANCE_HISTORY_DEFAULT_DAYS, DEFAULT_PAGE_SIZE, KIOSK_ALLOWED_IPS, MAX_OFFSET, MAX_PAGE_SIZE, STATIC_DIR, asset_fingerprint
from app.database.session import get_db
from app.schemas.attendance import AttendanceCorrectionRequest, AttendanceManualBatchRequest, AttendanceManualRequest, AttendanceOrigin, AttendanceScanRequest, ManualFrequentEmployeeRequest
from app.schemas.employee import EmpleadoOut
from app.models.employee import Empleado
from app.services.attendance_service import AttendanceError, EmployeeAccessDeniedError, add_manual_frequent_employee, attendance_summary, build_daily_report_payload, correct_attendance, dismiss_alert, get_attendance_since, inspector_dashboard, list_attendance, list_manual_frequent_employees, list_present_employees, preview_manual_batch, register_manual, register_manual_batch, register_scan, remove_manual_frequent_employee
from app.services.access_event_service import get_denied_events, list_denied_events, record_denied_event
from app.services.audit_service import list_audit_events
from app.services.notification_service import publish_exception_mark
from app.services.organization_service import get_organization_tree
from app.core.datetime_utils import LOCAL_TIMEZONE, to_local


router = APIRouter()
templates_env = Environment(
    loader=FileSystemLoader(str(STATIC_DIR.parent / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
)
templates_env.globals['asset_fingerprint'] = asset_fingerprint


def require_kiosk_station(request: Request) -> None:
    client_host = request.client.host if request.client else None
    if KIOSK_ALLOWED_IPS and client_host not in KIOSK_ALLOWED_IPS:
        raise HTTPException(status_code=403, detail='La estación no está autorizada para operar el kiosco.')


@router.get('/attendance', response_class=HTMLResponse)
def attendance_page(request: Request, user=Depends(require_manual_attendance)):
    template = templates_env.get_template('attendance.html')
    return HTMLResponse(template.render(active_page='attendance', user=user, csp_nonce=request.state.csp_nonce))


if APP_ENV != 'production':
    @router.get('/attendance/simulator', response_class=HTMLResponse)
    def attendance_simulator_page(request: Request, user=Depends(require_employee_manager)):
        template = templates_env.get_template('attendance_simulator.html')
        return HTMLResponse(template.render(active_page='attendance', user=user, csp_nonce=request.state.csp_nonce))


    @router.post('/api/attendance/simulator-scan')
    def attendance_simulator_scan(payload: AttendanceScanRequest, db: Session = Depends(get_db), _manager=Depends(require_employee_manager)):
        try:
            return register_scan(db, payload.codigo_tarjeta, AttendanceOrigin.PUERTO_COM)
        except EmployeeAccessDeniedError as exc:
            if not record_denied_event(db, exc):
                raise HTTPException(status_code=503, detail='No se pudo registrar la alerta de acceso.')
            return JSONResponse(status_code=403, content={
                'code': 'employee_access_denied',
                'detail': str(exc),
                'empleado_nombre': exc.employee_name,
                'estado': exc.employee_status,
                'fecha_hora': to_local(exc.marked_at).isoformat() if exc.marked_at else None,
            })
        except AttendanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc))


@router.get('/attendance/kiosk', response_class=HTMLResponse)
def attendance_kiosk_page(request: Request, user=Depends(require_user)):
    require_kiosk_station(request)
    template = templates_env.get_template('attendance_kiosk.html')
    return HTMLResponse(template.render(
        user=user,
        csp_nonce=request.state.csp_nonce,
        is_developer=user.rol == 'Desarrollador',
        is_inspector=user.rol == 'Inspector',
    ))


@router.get('/attendance/history', response_class=HTMLResponse)
def attendance_history_page(request: Request, user=Depends(require_page_user)):
    template = templates_env.get_template('attendance_history.html')
    return HTMLResponse(template.render(request=request, active_page='attendance_history', user=user, csp_nonce=request.state.csp_nonce, attendance_history_default_days=ATTENDANCE_HISTORY_DEFAULT_DAYS, attendance_default_page_size=DEFAULT_PAGE_SIZE))


@router.get('/attendance/summary', response_class=HTMLResponse)
def attendance_summary_page(request: Request, user=Depends(require_page_user)):
    template = templates_env.get_template('attendance_summary.html')
    return HTMLResponse(template.render(request=request, active_page='attendance_summary', user=user, csp_nonce=request.state.csp_nonce))


@router.get('/garita', response_class=HTMLResponse)
def garita_launcher_page(request: Request, user=Depends(require_page_user)):
    template = templates_env.get_template('garita_launcher.html')
    return HTMLResponse(template.render(active_page='garita_launcher', user=user, csp_nonce=request.state.csp_nonce))


@router.post('/api/attendance/kiosk-scan')
def kiosk_scan(request: Request, payload: AttendanceScanRequest, db: Session = Depends(get_db), _user=Depends(require_permission(PERMISSION_ACCESS_KIOSK))):
    require_kiosk_station(request)
    try:
        return register_scan(db, payload.codigo_tarjeta, AttendanceOrigin.PUERTO_COM)
    except EmployeeAccessDeniedError as exc:
        if not record_denied_event(db, exc):
            raise HTTPException(status_code=503, detail='No se pudo registrar la alerta de acceso.')
        return JSONResponse(status_code=403, content={
            'code': 'employee_access_denied',
            'detail': str(exc),
            'empleado_nombre': exc.employee_name,
            'estado': exc.employee_status,
        })
    except AttendanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post('/api/attendance/manual-mark')
def manual_mark(payload: AttendanceManualRequest, db: Session = Depends(get_db), _manager=Depends(require_manual_attendance)):
    try:
        result = register_manual(db, payload.empleado_id, _manager.id, payload.fecha_hora, payload.tipo, payload.operacion_id)
        if not result.codigo_tarjeta:
            publish_exception_mark(db, result.empleado_nombre, result.empleado_id)
            db.commit()
        return result
    except AttendanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post('/api/attendance/manual-mark/batch')
def manual_mark_batch(payload: AttendanceManualBatchRequest, db: Session = Depends(get_db), _manager=Depends(require_manual_attendance)):
    return register_manual_batch(db, payload.marcajes, _manager.id)


@router.post('/api/attendance/manual-mark/preview')
def manual_mark_preview(payload: AttendanceManualBatchRequest, db: Session = Depends(get_db), _manager=Depends(require_manual_attendance)):
    return {'types': preview_manual_batch(db, payload.marcajes)}


@router.get('/api/attendance/manual-frequent-employees')
def manual_frequent_employees(db: Session = Depends(get_db), _manager=Depends(require_manual_attendance)):
    return {'items': [EmpleadoOut.model_validate(employee) for employee in list_manual_frequent_employees(db, _manager.id)]}


@router.post('/api/attendance/manual-frequent-employees')
def add_manual_frequent(payload: ManualFrequentEmployeeRequest, db: Session = Depends(get_db), _manager=Depends(require_manual_attendance)):
    try:
        employee = add_manual_frequent_employee(db, _manager.id, payload.empleado_id, payload.posicion)
        return {'item': EmpleadoOut.model_validate(employee)}
    except EmployeeAccessDeniedError as exc:
        raise HTTPException(status_code=409, detail=f'{exc.employee_name}: {exc}')
    except AttendanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete('/api/attendance/manual-frequent-employees/{empleado_id}')
def delete_manual_frequent(empleado_id: int, db: Session = Depends(get_db), _manager=Depends(require_manual_attendance)):
    if not remove_manual_frequent_employee(db, _manager.id, empleado_id):
        raise HTTPException(status_code=404, detail='Empleado frecuente no encontrado.')
    return {'ok': True}


@router.patch('/api/attendance/{record_id}/correct')
def correct_attendance_route(record_id: int, payload: AttendanceCorrectionRequest, db: Session = Depends(get_db), _manager=Depends(require_employee_manager)):
    try:
        return correct_attendance(db, record_id, _manager.id, payload.motivo, payload.empleado_id, payload.fecha_hora, payload.tipo)
    except AttendanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get('/api/attendance/history')
def attendance_history(
    page: int = Query(1, ge=1), page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    date_from: date | None = None, date_to: date | None = None,
    empleado_q: str | None = Query(None, max_length=150), empleado_ids: list[int] | None = Query(None),
    departamento_ids: list[int] | None = Query(None), gerencia_ids: list[int] | None = Query(None), tipo: str | None = Query(None), tipo_nomina: str | None = Query(None, max_length=50),
    db: Session = Depends(get_db), _user=Depends(require_read_access),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail='La fecha inicial no puede ser posterior a la fecha final.')
    if (page - 1) * page_size > MAX_OFFSET:
        raise HTTPException(status_code=422, detail='La página solicitada supera el límite permitido.')
    return list_attendance(db, page, page_size, date_from, date_to, empleado_q, empleado_ids, departamento_ids, gerencia_ids, tipo, tipo_nomina)


@router.get('/api/attendance/export.csv')
def attendance_export(
    date_from: date | None = None, date_to: date | None = None,
    empleado_q: str | None = Query(None, max_length=150), empleado_ids: list[int] | None = Query(None),
    departamento_ids: list[int] | None = Query(None), gerencia_ids: list[int] | None = Query(None), tipo: str | None = Query(None), tipo_nomina: str | None = Query(None, max_length=50),
    db: Session = Depends(get_db), _user=Depends(require_read_access),
):
    page = 1
    items = []
    while True:
        history = list_attendance(db, page, MAX_PAGE_SIZE, date_from, date_to, empleado_q, empleado_ids, departamento_ids, gerencia_ids, tipo, tipo_nomina)
        items.extend(history.items)
        if len(history.items) < MAX_PAGE_SIZE:
            break
        page += 1
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['fecha_hora', 'empleado', 'cedula', 'departamento', 'cargo', 'tipo', 'origen'])
    for item in items:
        writer.writerow([item.fecha_hora.isoformat() if item.fecha_hora else '', item.empleado_nombre, item.cedula, item.departamento, item.cargo, item.tipo, item.origen])
    response = StreamingResponse(iter([output.getvalue()]), media_type='text/csv; charset=utf-8')
    response.headers['Content-Disposition'] = 'attachment; filename=marcajes_operativos.csv'
    return response


@router.get('/api/attendance/summary')
def attendance_summary_route(db: Session = Depends(get_db), _user=Depends(require_read_access)):
    return attendance_summary(db)


@router.get('/api/attendance/daily-report')
def attendance_daily_report(db: Session = Depends(get_db), _user=Depends(require_read_access)):
    report_date = datetime.now(LOCAL_TIMEZONE).date()
    day_start = datetime.combine(report_date, datetime.min.time(), tzinfo=LOCAL_TIMEZONE)
    summary = attendance_summary(db)
    today_records = list_attendance(db, page=1, page_size=25, date_from=report_date, date_to=report_date)
    recent_audit = list_audit_events(db, since=day_start, limit=20)
    return build_daily_report_payload(
        summary,
        [
            {'id': item.id, 'tipo': item.tipo.value if hasattr(item.tipo, 'value') else item.tipo, 'fecha_hora': item.fecha_hora.isoformat()}
            for item in today_records.items
        ],
        [
            {'id': record.id, 'accion': record.accion, 'entidad': record.entidad, 'fecha': record.fecha.isoformat() if record.fecha else None}
            for record in recent_audit
        ],
        report_date=report_date.isoformat(),
    )


@router.get('/api/attendance/present')
def attendance_present_route(db: Session = Depends(get_db), _user=Depends(require_read_access)):
    return list_present_employees(db)


@router.get('/api/attendance/inspector-dashboard')
def inspector_dashboard_route(db: Session = Depends(get_db), _user=Depends(require_read_access)):
    try:
        return inspector_dashboard(db, _user.id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail='El dashboard no está disponible temporalmente.') from exc


@router.post('/api/attendance/alerts/{alert_identifier}/dismiss')
def dismiss_attendance_alert(alert_identifier: str, db: Session = Depends(get_db), _user=Depends(require_read_access)):
    if len(alert_identifier) != 64 or any(character not in '0123456789abcdef' for character in alert_identifier.lower()):
        raise HTTPException(status_code=422, detail='Identificador de alerta inválido.')
    dismiss_alert(db, _user.id, alert_identifier.lower())
    return {'ok': True}


@router.get('/api/attendance/latest')
def attendance_latest_route(
    after_id: int | None = Query(None, ge=0),
    denied_after_id: int | None = Query(0, ge=0),
    db: Session = Depends(get_db), _user=Depends(require_read_access),
):
    records = get_attendance_since(db, after_id, AttendanceOrigin.PUERTO_COM)
    denied = get_denied_events(db, denied_after_id or 0)
    return {'items': records, 'item': records[-1] if records else None, 'denied': denied}


@router.get('/api/attendance/denied-events')
def attendance_denied_events(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db), _user=Depends(require_read_access),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail='La fecha inicial no puede ser posterior a la fecha final.')
    return {'items': list_denied_events(db, date_from, date_to)}


@router.get('/api/attendance/filter-options')
def attendance_filter_options(db: Session = Depends(get_db), _user=Depends(require_read_access)):
    tree = get_organization_tree(db)
    gerencias = [{'id': item['id'], 'nombre': item['nombre']} for item in tree]
    departamentos = [
        {'id': department['id'], 'nombre': department['nombre'], 'gerencia_id': item['id']}
        for item in tree for department in item.get('departamentos', [])
    ]
    payroll_types = [value for (value,) in db.query(Empleado.tipo_nomina).filter(Empleado.tipo_nomina.isnot(None)).distinct().order_by(Empleado.tipo_nomina.asc()).all()]
    return {'gerencias': gerencias, 'departamentos': departamentos, 'tipo_nomina': payroll_types}