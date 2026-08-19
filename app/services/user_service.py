from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import Usuario
from app.schemas.user import UsuarioCreate, UsuarioUpdate


ROLE_ADMIN = 'Administrador'


class UserNotFoundError(ValueError):
    pass


def normalize_username(username: str) -> str:
    return username.strip().lower()


def create_user(db: Session, payload: UsuarioCreate) -> Usuario:
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
        rol=ROLE_ADMIN,
        activo=1,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def list_users(db: Session, query: str | None = None):
    statement = db.query(Usuario)
    if query and query.strip():
        search = f'%{query.strip()}%'
        statement = statement.filter((Usuario.username.ilike(search)) | (Usuario.nombre.ilike(search)))
    return statement.order_by(Usuario.nombre.asc(), Usuario.username.asc()).all()


def update_user(db: Session, user_id: int, payload: UsuarioUpdate) -> Usuario:
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

    usuario.username = username
    usuario.nombre = nombre
    if payload.password:
        usuario.password_hash = hash_password(payload.password)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def set_user_status(db: Session, user_id: int, active: bool) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise UserNotFoundError('El usuario no existe.')
    usuario.activo = 1 if active else 0
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario
