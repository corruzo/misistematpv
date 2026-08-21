from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import Usuario
from app.services.auth_service import SESSION_COOKIE, get_user_by_token

ROLE_ADMIN = 'Administrador'
ROLE_HR = 'RRHH'
ROLE_VIEWER = 'Consulta'
ALL_ROLES = (ROLE_ADMIN, ROLE_HR, ROLE_VIEWER)


def current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario | None:
    return get_user_by_token(db, request.cookies.get(SESSION_COOKIE))


def require_user(user: Usuario | None = Depends(current_user_optional)) -> Usuario:
    if not user:
        raise HTTPException(status_code=401, detail='Debes iniciar sesión.')
    return user


def require_roles(*roles: str):
    def dependency(user: Usuario = Depends(require_user)) -> Usuario:
        if user.rol not in roles:
            raise HTTPException(status_code=403, detail='No tienes permisos para realizar esta operación.')
        return user
    return dependency


def require_admin(user: Usuario = Depends(require_user)) -> Usuario:
    if user.rol != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail='No tienes permisos para realizar esta operación.')
    return user


def require_employee_manager(user: Usuario = Depends(require_user)) -> Usuario:
    return require_roles(ROLE_ADMIN, ROLE_HR)(user)


def require_read_access(user: Usuario = Depends(require_user)) -> Usuario:
    return require_roles(*ALL_ROLES)(user)


def require_page_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    user = get_user_by_token(db, request.cookies.get(SESSION_COOKIE))
    if not user:
        raise HTTPException(status_code=307, headers={'Location': '/login'})
    return user
