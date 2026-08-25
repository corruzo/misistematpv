from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, MAX_OFFSET, STATIC_DIR
from app.core.auth import require_admin, require_page_user, require_user
from app.database.session import get_db
from app.schemas.user import UsuarioCreate, UsuarioOut, UsuarioPage, UsuarioStatusUpdate, UsuarioUpdate
from app.services.user_service import count_users, create_user, list_users, set_user_status, update_user, UserNotFoundError

router = APIRouter()
templates_env = Environment(
    loader=FileSystemLoader(str(STATIC_DIR.parent / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
)


def user_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IntegrityError):
        return HTTPException(status_code=409, detail='Ya existe un usuario con ese nombre.')
    if isinstance(exc, SQLAlchemyError):
        return HTTPException(status_code=503, detail='No se pudo completar la operación en la base de datos.')
    return HTTPException(status_code=400, detail='La operación no es válida.')


@router.get('/users', response_class=HTMLResponse)
def users_page(request: Request, user=Depends(require_admin)):
    template = templates_env.get_template('users.html')
    return HTMLResponse(template.render(active_page='users', user=user, csp_nonce=request.state.csp_nonce, default_page_size=DEFAULT_PAGE_SIZE))


@router.get('/profile', response_class=HTMLResponse)
def profile_page(request: Request, user=Depends(require_page_user)):
    template = templates_env.get_template('profile.html')
    return HTMLResponse(template.render(active_page='profile', user=user, csp_nonce=request.state.csp_nonce))


@router.get('/api/me', response_model=UsuarioOut)
def api_me(user=Depends(require_user)):
    return UsuarioOut.from_model(user)


@router.put('/api/me', response_model=UsuarioOut)
def api_update_me(payload: UsuarioUpdate, user=Depends(require_user), db: Session = Depends(get_db)):
    from app.services.auth_service import update_own_profile
    try:
        return UsuarioOut.from_model(update_own_profile(db, user, payload.username, payload.nombre, payload.password))
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise user_error(exc)


@router.get('/api/users', response_model=UsuarioPage)
def api_list_users(
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1), page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db), _admin=Depends(require_admin),
):
    try:
        offset = min((page - 1) * page_size, MAX_OFFSET)
        users = [UsuarioOut.from_model(user) for user in list_users(db, q, page_size, offset)]
        return {'items': users, 'total': count_users(db, q), 'page': page, 'page_size': page_size}
    except SQLAlchemyError as exc:
        db.rollback()
        raise user_error(exc)


@router.post('/api/users', response_model=UsuarioOut, status_code=201)
def api_create_user(payload: UsuarioCreate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    try:
        return UsuarioOut.from_model(create_user(db, payload, _admin.id))
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise user_error(exc)


@router.put('/api/users/{user_id}', response_model=UsuarioOut)
def api_update_user(user_id: int, payload: UsuarioUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    try:
        return UsuarioOut.from_model(update_user(db, user_id, payload, _admin.id))
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise user_error(exc)


@router.patch('/api/users/{user_id}/status', response_model=UsuarioOut)
def api_update_user_status(user_id: int, payload: UsuarioStatusUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    try:
        return UsuarioOut.from_model(set_user_status(db, user_id, payload.activo, _admin.id))
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ValueError, IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        raise user_error(exc)
