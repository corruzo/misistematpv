from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.auth import require_page_user
from app.schemas.employee import EmpleadoCreate, EmpleadoOut, EmpleadoUpdate
from app.schemas.organization import GerenciaCreate, DepartamentoCreate, CargoCreate, OrganizationStatusUpdate
from app.services.employee_service import (
    create_employee,
    search_employees,
    count_employees,
    get_employee_by_id,
    update_employee,
    soft_delete_employee,
    get_employee_metrics,
)
from app.services.organization_service import (
    get_organization_tree,
    create_gerencia,
    create_departamento,
    create_cargo,
    set_organization_state,
    Gerencia,
    Departamento,
    Cargo,
)
from app.core.config import STATIC_DIR

router = APIRouter()


def organization_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IntegrityError):
        return HTTPException(status_code=409, detail='Ya existe un registro con ese nombre o hay una relación duplicada.')
    if isinstance(exc, SQLAlchemyError):
        return HTTPException(status_code=503, detail='No se pudo completar la operación en la base de datos.')
    return HTTPException(status_code=400, detail=str(exc) or 'La operación no es válida.')

templates_env = Environment(
    loader=FileSystemLoader(str(STATIC_DIR.parent / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
)


@router.get('/')
def index(user=Depends(require_page_user)):
    tpl = templates_env.get_template('index.html')
    content = tpl.render(active_page='dashboard', user=user)
    return HTMLResponse(content)


@router.get('/employees')
def employees_page(user=Depends(require_page_user)):
    tpl = templates_env.get_template('employees.html')
    content = tpl.render(active_page='employees', user=user)
    return HTMLResponse(content)


@router.get('/organization')
def organization_page(user=Depends(require_page_user)):
    tpl = templates_env.get_template('organization.html')
    content = tpl.render(active_page='organization', user=user)
    return HTMLResponse(content)


@router.get('/api/organization')
def api_get_organization(db: Session = Depends(get_db)):
    return get_organization_tree(db)


@router.get('/api/system/status')
def api_get_system_status(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
        return {'connected': True, 'message': 'Base de datos conectada'}
    except Exception as exc:
        return {'connected': False, 'message': 'Falla de conexión a la base de datos', 'detail': str(exc)}


@router.get('/api/employees/{emp_id}')
def api_get_employee_by_id_route(emp_id: int, db: Session = Depends(get_db)):
    emp = get_employee_by_id(db, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail='Empleado no encontrado')
    return EmpleadoOut.model_validate(emp)


@router.get('/api/dashboard/metrics')
def api_get_dashboard_metrics(db: Session = Depends(get_db)):
    return get_employee_metrics(db)


@router.post('/api/organization/gerencias')
def api_create_gerencia_route(payload: GerenciaCreate, db: Session = Depends(get_db)):
    try:
        return create_gerencia(db, payload)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.post('/api/organization/departamentos')
def api_create_departamento_route(payload: DepartamentoCreate, db: Session = Depends(get_db)):
    try:
        return create_departamento(db, payload)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.post('/api/organization/cargos')
def api_create_cargo_route(payload: CargoCreate, db: Session = Depends(get_db)):
    try:
        return create_cargo(db, payload)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.patch('/api/organization/gerencias/{gerencia_id}/status')
def api_update_gerencia_status(gerencia_id: int, payload: OrganizationStatusUpdate, db: Session = Depends(get_db)):
    try:
        return set_organization_state(db, Gerencia, gerencia_id, payload.estado)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.patch('/api/organization/departamentos/{departamento_id}/status')
def api_update_departamento_status(departamento_id: int, payload: OrganizationStatusUpdate, db: Session = Depends(get_db)):
    try:
        return set_organization_state(db, Departamento, departamento_id, payload.estado)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.patch('/api/organization/cargos/{cargo_id}/status')
def api_update_cargo_status(cargo_id: int, payload: OrganizationStatusUpdate, db: Session = Depends(get_db)):
    try:
        return set_organization_state(db, Cargo, cargo_id, payload.estado)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.get('/api/employees')
def api_get_employees(
    q: Optional[str] = None,
    estado: Optional[str] = None,
    gerencia: Optional[str] = None,
    departamento: Optional[str] = None,
    tipo_nomina: Optional[str] = None,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    db: Session = Depends(get_db)
):
    emps = search_employees(
        db,
        q=q,
        estado=estado,
        gerencia=gerencia,
        departamento=departamento,
        tipo_nomina=tipo_nomina,
        limit=limit,
        offset=offset,
    )
    payload = [EmpleadoOut.model_validate(e) for e in emps]
    total = count_employees(db, q=q, estado=estado, gerencia=gerencia, departamento=departamento, tipo_nomina=tipo_nomina)
    return {
        'items': payload,
        'total': total,
        'metrics': get_employee_metrics(db),
    }


@router.post('/api/employees')
async def api_create_employee(
    cedula: str = Form(...),
    nombre_apellido: str = Form(...),
    gerencia: str = Form(...),
    departamento: str = Form(...),
    cargo: str = Form(...),
    gerencia_id: Optional[int] = Form(None),
    departamento_id: Optional[int] = Form(None),
    cargo_id: Optional[int] = Form(None),
    estado: str = Form('Activo'),
    tipo_nomina: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    payload = EmpleadoCreate(
        cedula=cedula,
        nombre_apellido=nombre_apellido,
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
        emp = create_employee(db, payload, foto)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        if isinstance(exc, IntegrityError):
            raise HTTPException(status_code=409, detail='Ya existe un empleado con esa cédula.')
        raise organization_error(exc)
    return EmpleadoOut.model_validate(emp)


@router.put('/api/employees/{emp_id}')
async def api_update_employee(
    emp_id: int,
    nombre_apellido: Optional[str] = Form(None),
    gerencia: Optional[str] = Form(None),
    departamento: Optional[str] = Form(None),
    cargo: Optional[str] = Form(None),
    gerencia_id: Optional[int] = Form(None),
    departamento_id: Optional[int] = Form(None),
    cargo_id: Optional[int] = Form(None),
    estado: Optional[str] = Form(None),
    tipo_nomina: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    emp = get_employee_by_id(db, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail='Empleado no encontrado')
    updates = EmpleadoUpdate(
        nombre_apellido=nombre_apellido,
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
        emp = update_employee(db, emp, updates, foto)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        if isinstance(exc, IntegrityError):
            raise HTTPException(status_code=409, detail='No se pudo actualizar: la cédula ya está registrada.')
        raise organization_error(exc)
    return EmpleadoOut.model_validate(emp)


@router.patch('/api/employees/{emp_id}/disable')
def api_disable_employee(emp_id: int, db: Session = Depends(get_db)):
    emp = get_employee_by_id(db, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail='Empleado no encontrado')
    try:
        emp = soft_delete_employee(db, emp)
    except SQLAlchemyError as exc:
        db.rollback()
        raise organization_error(exc)
    return EmpleadoOut.model_validate(emp)