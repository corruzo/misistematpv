from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.auth import require_employee_manager, require_manual_attendance, require_read_access
from app.schemas.employee import EmpleadoCreate, EmpleadoManualOut, EmpleadoOperativoOut, EmpleadoOut, EmpleadoUpdate
from app.services.employee_service import (
    create_employee,
    search_employees,
    count_employees,
    get_employee_by_id,
    get_employee_profile,
    update_employee,
    soft_delete_employee,
    get_employee_metrics,
)
from app.core.config import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE, STATIC_DIR

router = APIRouter()


templates_env = Environment(
    loader=FileSystemLoader(str(STATIC_DIR.parent / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
)


@router.get('/employees')
def employees_page(request: Request, user=Depends(require_read_access)):
    tpl = templates_env.get_template('employees.html')
    content = tpl.render(active_page='employees', user=user, csp_nonce=request.state.csp_nonce)
    return HTMLResponse(content)


@router.get('/api/employees/{emp_id}')
def api_get_employee_by_id_route(emp_id: int, db: Session = Depends(get_db), _user=Depends(require_read_access)):
    if _user.rol == 'Inspector':
        raise HTTPException(status_code=403, detail='El Inspector no puede consultar fichas individuales.')
    emp = get_employee_by_id(db, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail='Empleado no encontrado')
    return EmpleadoOut.model_validate(emp)


@router.get('/api/employees')
def api_get_employees(
    q: Optional[str] = None,
    estado: Optional[str] = None,
    gerencia: Optional[str] = None,
    departamento: Optional[str] = None,
    gerencia_id: Optional[int] = None,
    departamento_id: Optional[int] = None,
    tipo_nomina: Optional[str] = None,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    db: Session = Depends(get_db), _user=Depends(require_read_access)
):
    emps = search_employees(
        db,
        q=q,
        estado=estado,
        gerencia=gerencia,
        departamento=departamento,
        gerencia_id=gerencia_id,
        departamento_id=departamento_id,
        tipo_nomina=tipo_nomina,
        limit=limit,
        offset=offset,
    )
    payload = [
        EmpleadoOperativoOut.model_validate(e) if _user.rol == 'Inspector' else EmpleadoOut.model_validate(e)
        for e in emps
    ]
    total = count_employees(db, q=q, estado=estado, gerencia=gerencia, departamento=departamento, gerencia_id=gerencia_id, departamento_id=departamento_id, tipo_nomina=tipo_nomina)
    return {
        'items': payload,
        'total': total,
        'metrics': get_employee_metrics(db),
    }


@router.get('/api/attendance/manual-employees')
def api_get_manual_employees(
    q: Optional[str] = Query(None, max_length=150),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db), _user=Depends(require_manual_attendance),
):
    emps = search_employees(db, q=q, limit=limit, offset=0)
    return {'items': [EmpleadoManualOut.model_validate(employee) for employee in emps]}


@router.post('/api/employees')
async def api_create_employee(
    cedula: str = Form(...),
    codigo_tarjeta: Optional[str] = Form(None),
    nombre_apellido: str = Form(...),
    fecha_nacimiento: Optional[date] = Form(None),
    telefono: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    contacto_emergencia_parentesco: Optional[str] = Form(None),
    contacto_emergencia_telefono: Optional[str] = Form(None),
    gerencia: str = Form(...),
    departamento: str = Form(...),
    cargo: str = Form(...),
    gerencia_id: Optional[int] = Form(None),
    departamento_id: Optional[int] = Form(None),
    cargo_id: Optional[int] = Form(None),
    estado: str = Form('Activo'),
    tipo_nomina: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db), _manager=Depends(require_employee_manager)
):
    payload = EmpleadoCreate(
        cedula=cedula,
        codigo_tarjeta=codigo_tarjeta,
        nombre_apellido=nombre_apellido,
        fecha_nacimiento=fecha_nacimiento,
        telefono=telefono,
        email=email,
        contacto_emergencia_parentesco=contacto_emergencia_parentesco,
        contacto_emergencia_telefono=contacto_emergencia_telefono,
        gerencia=gerencia,
        departamento=departamento,
        cargo=cargo,
        gerencia_id=gerencia_id,
        departamento_id=departamento_id,
        cargo_id=cargo_id,
        estado=estado,
        tipo_nomina=tipo_nomina,
    )
    try:
        emp = create_employee(db, payload, foto, _manager.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        if isinstance(exc, IntegrityError):
            raise HTTPException(status_code=409, detail='Ya existe un empleado con esa cédula.')
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=400, detail=str(exc))
        raise organization_error(exc)
    return EmpleadoOut.model_validate(emp)


@router.put('/api/employees/{emp_id}')
async def api_update_employee(
    emp_id: int,
    codigo_tarjeta: Optional[str] = Form(None),
    nombre_apellido: Optional[str] = Form(None),
    fecha_nacimiento: Optional[date] = Form(None),
    telefono: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    contacto_emergencia_parentesco: Optional[str] = Form(None),
    contacto_emergencia_telefono: Optional[str] = Form(None),
    gerencia: Optional[str] = Form(None),
    departamento: Optional[str] = Form(None),
    cargo: Optional[str] = Form(None),
    gerencia_id: Optional[int] = Form(None),
    departamento_id: Optional[int] = Form(None),
    cargo_id: Optional[int] = Form(None),
    estado: Optional[str] = Form(None),
    tipo_nomina: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    eliminar_foto: str = Form('false'),
    db: Session = Depends(get_db), _manager=Depends(require_employee_manager)
):
    emp = get_employee_by_id(db, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail='Empleado no encontrado')
    updates = EmpleadoUpdate(
        nombre_apellido=nombre_apellido,
        codigo_tarjeta=codigo_tarjeta,
        fecha_nacimiento=fecha_nacimiento,
        telefono=telefono,
        email=email,
        contacto_emergencia_parentesco=contacto_emergencia_parentesco,
        contacto_emergencia_telefono=contacto_emergencia_telefono,
        gerencia=gerencia,
        departamento=departamento,
        cargo=cargo,
        gerencia_id=gerencia_id,
        departamento_id=departamento_id,
        cargo_id=cargo_id,
        estado=estado,
        tipo_nomina=tipo_nomina,
    )
    try:
        remove_photo = eliminar_foto.strip().lower() in {'true', '1', 'on', 'yes'}
        emp = update_employee(db, emp, updates, foto, eliminar_foto=remove_photo, usuario_id=_manager.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        if isinstance(exc, IntegrityError):
            raise HTTPException(status_code=409, detail='No se pudo actualizar: la cédula o el código RFID ya están registrados.')
        raise organization_error(exc)
    return EmpleadoOut.model_validate(emp)


@router.patch('/api/employees/{emp_id}/disable')
def api_disable_employee(emp_id: int, db: Session = Depends(get_db), _manager=Depends(require_employee_manager)):
    emp = get_employee_by_id(db, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail='Empleado no encontrado')
    try:
        emp = soft_delete_employee(db, emp, _manager.id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise organization_error(exc)
    return EmpleadoOut.model_validate(emp)


@router.get('/api/employees/{emp_id}/profile')
def api_get_employee_profile_route(
    emp_id: int,
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db), _user=Depends(require_read_access),
):
    if _user.rol == 'Inspector':
        raise HTTPException(status_code=403, detail='El Inspector no puede consultar fichas individuales.')
    profile = get_employee_profile(db, emp_id, days=days, page=page, page_size=page_size)
    if not profile:
        raise HTTPException(status_code=404, detail='Empleado no encontrado')
    return profile


@router.get('/api/system/status')
def api_get_system_status(db: Session = Depends(get_db), _user=Depends(require_read_access)):
    try:
        db.execute(text('SELECT 1'))
        return {'connected': True, 'message': 'Base de datos conectada'}
    except Exception:
        return {'connected': False, 'message': 'Falla de conexión a la base de datos'}