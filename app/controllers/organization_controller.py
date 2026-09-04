from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import require_developer, require_read_access
from app.core.config import STATIC_DIR
from app.database.session import get_db
from app.schemas.organization import GerenciaCreate, DepartamentoCreate, CargoCreate, OrganizationStatusUpdate, OrganizationUpdate, OrganizationDeleteResult
from app.services.organization_service import (
    get_organization_tree,
    create_gerencia,
    create_departamento,
    create_cargo,
    set_organization_state,
    update_organization,
    delete_or_disable_organization,
    Gerencia,
    Departamento,
    Cargo,
)

router = APIRouter()
templates_env = Environment(
    loader=FileSystemLoader(str(STATIC_DIR.parent / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
)
from app.core.config import asset_fingerprint
templates_env.globals['asset_fingerprint'] = asset_fingerprint


def organization_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IntegrityError):
        return HTTPException(status_code=409, detail='Ya existe un registro con ese nombre o hay una relación duplicada.')
    if isinstance(exc, SQLAlchemyError):
        return HTTPException(status_code=503, detail='No se pudo completar la operación en la base de datos.')
    return HTTPException(status_code=400, detail='La operación no es válida.')


@router.get('/organization')
def organization_page(request: Request, user=Depends(require_developer)):
    template = templates_env.get_template('organization.html')
    return HTMLResponse(template.render(active_page='organization', user=user, csp_nonce=request.state.csp_nonce))


@router.get('/api/organization')
def api_get_organization(db: Session = Depends(get_db), _user=Depends(require_read_access)):
    return get_organization_tree(db)


@router.post('/api/organization/gerencias')
def api_create_gerencia_route(payload: GerenciaCreate, db: Session = Depends(get_db), _admin=Depends(require_developer)):
    try:
        return create_gerencia(db, payload, _admin.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.post('/api/organization/departamentos')
def api_create_departamento_route(payload: DepartamentoCreate, db: Session = Depends(get_db), _admin=Depends(require_developer)):
    try:
        return create_departamento(db, payload, _admin.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.post('/api/organization/cargos')
def api_create_cargo_route(payload: CargoCreate, db: Session = Depends(get_db), _admin=Depends(require_developer)):
    try:
        return create_cargo(db, payload, _admin.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.patch('/api/organization/gerencias/{gerencia_id}/status')
def api_update_gerencia_status(gerencia_id: int, payload: OrganizationStatusUpdate, db: Session = Depends(get_db), _admin=Depends(require_developer)):
    try:
        return set_organization_state(db, Gerencia, gerencia_id, payload.estado, _admin.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.patch('/api/organization/departamentos/{departamento_id}/status')
def api_update_departamento_status(departamento_id: int, payload: OrganizationStatusUpdate, db: Session = Depends(get_db), _admin=Depends(require_developer)):
    try:
        return set_organization_state(db, Departamento, departamento_id, payload.estado, _admin.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.patch('/api/organization/cargos/{cargo_id}/status')
def api_update_cargo_status(cargo_id: int, payload: OrganizationStatusUpdate, db: Session = Depends(get_db), _admin=Depends(require_developer)):
    try:
        return set_organization_state(db, Cargo, cargo_id, payload.estado, _admin.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


def organization_model(type_name: str):
    models = {'gerencia': Gerencia, 'departamento': Departamento, 'cargo': Cargo}
    model = models.get(type_name)
    if not model:
        raise HTTPException(status_code=404, detail='Tipo de estructura no válido.')
    return model


@router.put('/api/organization/{type_name}/{item_id}')
def api_update_organization(type_name: str, item_id: int, payload: OrganizationUpdate, db: Session = Depends(get_db), _admin=Depends(require_developer)):
    try:
        return update_organization(db, organization_model(type_name), item_id, payload, _admin.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)


@router.delete('/api/organization/{type_name}/{item_id}', response_model=OrganizationDeleteResult)
def api_delete_organization(type_name: str, item_id: int, db: Session = Depends(get_db), _admin=Depends(require_developer)):
    try:
        return delete_or_disable_organization(db, organization_model(type_name), item_id, _admin.id)
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise organization_error(exc)
