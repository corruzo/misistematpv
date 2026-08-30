from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.auth import ROLE_DEVELOPER
from app.models.user import Usuario
from app.services.auth_service import invalidate_user_sessions
from app.schemas.user import UsuarioCreate, UsuarioUpdate
from app.services.audit_service import add_audit
from app.services.notification_service import publish_user_changed


class UserNotFoundError(ValueError):
    pass


def normalize_username(username: str) -> str:
    return username.strip().lower()


def create_user(db: Session, payload: UsuarioCreate, actor_id: int | None = None) -> Usuario:
    username = normalize_username(payload.username)
    nombre = payload.nombre.strip()
    if not username or not nombre:
        raise ValueError('El usuario y el nombre son obligatorios.')
    if db.query(Usuario).filter(Usuario.username == username).first():
        raise ValueError(f'Ya existe el nombre de usuario "{username}".')

    usuario = Usuario(
        username=username,
        nombre=nombre,
        password_hash=hash_password(payload.password),
        rol=payload.rol,
        activo=1,
    )
    db.add(usuario)
    db.flush()
    add_audit(db, actor_id, 'alta', 'usuarios', usuario.id, despues={'username': usuario.username, 'nombre': usuario.nombre, 'rol': usuario.rol, 'activo': True})
    publish_user_changed(db, usuario.username, 'creó', actor_id)
    db.commit()
    db.refresh(usuario)
    return usuario


def build_user_query(db: Session, query: str | None = None):
    statement = db.query(Usuario)
    if query and query.strip():
        search = f'%{query.strip()}%'
        statement = statement.filter((Usuario.username.like(search)) | (Usuario.nombre.like(search)))
    return statement


def list_users(db: Session, query: str | None = None, limit: int = 25, offset: int = 0):
    return build_user_query(db, query).order_by(Usuario.nombre.asc(), Usuario.username.asc()).offset(offset).limit(limit).all()


def count_users(db: Session, query: str | None = None) -> int:
    return build_user_query(db, query).count()


def update_user(db: Session, user_id: int, payload: UsuarioUpdate, actor_id: int | None = None) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise UserNotFoundError('El usuario no existe.')

    username = normalize_username(payload.username)
    nombre = payload.nombre.strip()
    duplicate = db.query(Usuario).filter(Usuario.username == username, Usuario.id != user_id).first()
    if duplicate:
        raise ValueError('Ya existe otro usuario con ese nombre.')
    if not username or not nombre:
        raise ValueError('El usuario y el nombre son obligatorios.')
    previous_role = usuario.rol
    previous_active = bool(usuario.activo)
    if actor_id == usuario.id and payload.rol != ROLE_DEVELOPER:
        raise ValueError('No puedes quitarte el rol de Desarrollador.')
    if previous_role == ROLE_DEVELOPER and payload.rol != ROLE_DEVELOPER and previous_active and db.query(Usuario).filter(Usuario.rol == ROLE_DEVELOPER, Usuario.activo == 1, Usuario.id != user_id).count() < 1:
        raise ValueError('Debe existir al menos un Desarrollador activo.')
    if payload.activo is False and actor_id == usuario.id:
        raise ValueError('No puedes inhabilitar tu propio usuario.')
    if payload.activo is False and previous_role == ROLE_DEVELOPER and previous_active and payload.rol == ROLE_DEVELOPER and db.query(Usuario).filter(Usuario.rol == ROLE_DEVELOPER, Usuario.activo == 1, Usuario.id != user_id).count() < 1:
        raise ValueError('Debe existir al menos un Desarrollador activo.')

    antes = {'username': usuario.username, 'nombre': usuario.nombre, 'rol': usuario.rol, 'activo': bool(usuario.activo)}
    usuario.username = username
    usuario.nombre = nombre
    usuario.rol = payload.rol
    if payload.activo is not None:
        usuario.activo = 1 if payload.activo else 0
        if not payload.activo:
            invalidate_user_sessions(db, usuario.id)
    if payload.password:
        usuario.password_hash = hash_password(payload.password)
        invalidate_user_sessions(db, usuario.id)
    db.add(usuario)
    add_audit(db, actor_id, 'actualizacion', 'usuarios', usuario.id, antes, {'username': usuario.username, 'nombre': usuario.nombre, 'rol': usuario.rol, 'activo': bool(usuario.activo)})
    publish_user_changed(db, usuario.username, 'actualizó', actor_id)
    db.commit()
    db.refresh(usuario)
    return usuario


def set_user_status(db: Session, user_id: int, active: bool, actor_id: int | None = None) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise UserNotFoundError('El usuario no existe.')
    if not active and actor_id == usuario.id:
        raise ValueError('No puedes inhabilitar tu propio usuario.')
    if not active and usuario.rol == ROLE_DEVELOPER and db.query(Usuario).filter(Usuario.rol == ROLE_DEVELOPER, Usuario.activo == 1).count() <= 1:
        raise ValueError('Debe existir al menos un Desarrollador activo.')
    antes = {'activo': bool(usuario.activo)}
    usuario.activo = 1 if active else 0
    if not active:
        invalidate_user_sessions(db, usuario.id)
    db.add(usuario)
    add_audit(db, actor_id, 'cambio_estado', 'usuarios', usuario.id, antes, {'activo': bool(usuario.activo)})
    publish_user_changed(db, usuario.username, 'inhabilitó' if not active else 'habilitó', actor_id)
    db.commit()
    db.refresh(usuario)
    return usuario
