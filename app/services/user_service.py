from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import Usuario
from app.schemas.user import UsuarioCreate, UsuarioUpdate
from app.services.audit_service import add_audit


ROLE_ADMIN = 'Administrador'


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
        raise ValueError('Ya existe un usuario con ese nombre.')

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
    db.commit()
    db.refresh(usuario)
    return usuario


def list_users(db: Session, query: str | None = None):
    statement = db.query(Usuario)
    if query and query.strip():
        search = f'%{query.strip()}%'
        statement = statement.filter((Usuario.username.like(search)) | (Usuario.nombre.like(search)))
    return statement.order_by(Usuario.nombre.asc(), Usuario.username.asc()).all()


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

    antes = {'username': usuario.username, 'nombre': usuario.nombre, 'rol': usuario.rol, 'activo': bool(usuario.activo)}
    usuario.username = username
    usuario.nombre = nombre
    usuario.rol = payload.rol
    if payload.password:
        usuario.password_hash = hash_password(payload.password)
    db.add(usuario)
    add_audit(db, actor_id, 'actualizacion', 'usuarios', usuario.id, antes, {'username': usuario.username, 'nombre': usuario.nombre, 'rol': usuario.rol, 'activo': bool(usuario.activo)})
    db.commit()
    db.refresh(usuario)
    return usuario


def set_user_status(db: Session, user_id: int, active: bool, actor_id: int | None = None) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise UserNotFoundError('El usuario no existe.')
    antes = {'activo': bool(usuario.activo)}
    usuario.activo = 1 if active else 0
    db.add(usuario)
    add_audit(db, actor_id, 'cambio_estado', 'usuarios', usuario.id, antes, {'activo': bool(usuario.activo)})
    db.commit()
    db.refresh(usuario)
    return usuario
