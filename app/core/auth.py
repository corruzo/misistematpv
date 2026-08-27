from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import Usuario
from app.services.auth_service import SESSION_COOKIE, get_user_by_token

ROLE_DEVELOPER = 'Desarrollador'
ROLE_HR = 'RRHH'
ROLE_INSPECTOR = 'Inspector'
ALL_ROLES = (ROLE_HR, ROLE_DEVELOPER, ROLE_INSPECTOR)

PERMISSION_READ_MASTER_DATA = 'master_data:read'
PERMISSION_MANAGE_EMPLOYEES = 'master_data:employees:manage'
PERMISSION_MANAGE_ORGANIZATION = 'master_data:organization:manage'
PERMISSION_MANAGE_USERS = 'master_data:users:manage'
PERMISSION_READ_ATTENDANCE = 'attendance:read'
PERMISSION_MANAGE_ATTENDANCE = 'attendance:manage'
PERMISSION_MANUAL_ATTENDANCE = 'attendance:manual_mark'
PERMISSION_ACCESS_KIOSK = 'attendance:kiosk'
PERMISSION_MANAGE_SYSTEM = 'system:manage'

ROLE_PERMISSIONS = {
    ROLE_DEVELOPER: frozenset({
        PERMISSION_READ_MASTER_DATA,
        PERMISSION_MANAGE_EMPLOYEES,
        PERMISSION_MANAGE_ORGANIZATION,
        PERMISSION_MANAGE_USERS,
        PERMISSION_READ_ATTENDANCE,
        PERMISSION_MANAGE_ATTENDANCE,
        PERMISSION_MANUAL_ATTENDANCE,
        PERMISSION_ACCESS_KIOSK,
        PERMISSION_MANAGE_SYSTEM,
    }),
    ROLE_HR: frozenset({
        PERMISSION_READ_MASTER_DATA,
        PERMISSION_MANAGE_EMPLOYEES,
        PERMISSION_READ_ATTENDANCE,
        PERMISSION_MANAGE_ATTENDANCE,
        PERMISSION_MANUAL_ATTENDANCE,
        PERMISSION_ACCESS_KIOSK,
    }),
    ROLE_INSPECTOR: frozenset({
        PERMISSION_READ_MASTER_DATA,
        PERMISSION_READ_ATTENDANCE,
        PERMISSION_MANUAL_ATTENDANCE,
        PERMISSION_ACCESS_KIOSK,
    }),
}


def current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario | None:
    return get_user_by_token(db, request.cookies.get(SESSION_COOKIE))


def require_user(request: Request, user: Usuario | None = Depends(current_user_optional)) -> Usuario:
    if not user:
        if not request.url.path.startswith('/api/'):
            raise HTTPException(status_code=307, headers={'Location': '/login?reason=session_expired'})
        raise HTTPException(status_code=401, detail='Debes iniciar sesión.')
    return user


def require_roles(*roles: str):
    def dependency(user: Usuario = Depends(require_user)) -> Usuario:
        if user.rol not in roles:
            raise HTTPException(status_code=403, detail='No tienes permisos para realizar esta operación.')
        return user
    return dependency


def has_permission(user: Usuario, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.rol, frozenset())


def require_permission(permission: str):
    def dependency(user: Usuario = Depends(require_user)) -> Usuario:
        if not has_permission(user, permission):
            raise HTTPException(status_code=403, detail='No tienes permisos para realizar esta operación.')
        return user
    return dependency


def require_developer(user: Usuario = Depends(require_user)) -> Usuario:
    return require_permission(PERMISSION_MANAGE_USERS)(user)


def require_employee_manager(user: Usuario = Depends(require_user)) -> Usuario:
    return require_permission(PERMISSION_MANAGE_EMPLOYEES)(user)


def require_manual_attendance(user: Usuario = Depends(require_user)) -> Usuario:
    return require_permission(PERMISSION_MANUAL_ATTENDANCE)(user)


def require_read_access(user: Usuario = Depends(require_user)) -> Usuario:
    return require_permission(PERMISSION_READ_MASTER_DATA)(user)



def require_page_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    user = get_user_by_token(db, request.cookies.get(SESSION_COOKIE))
    if not user:
        raise HTTPException(status_code=307, headers={'Location': '/login?reason=session_expired'})
    return user
