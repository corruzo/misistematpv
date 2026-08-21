import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password, password_needs_rehash, verify_password
from app.core.datetime_utils import utc_now
from app.models.auth_session import AuthSession
from app.models.user import Usuario
from app.services.audit_service import add_audit

SESSION_COOKIE = 'marcajetpv_session'
SESSION_HOURS = 12


def cleanup_expired_sessions(db: Session) -> int:
    deleted = db.query(AuthSession).filter(AuthSession.expires_at < utc_now()).delete(synchronize_session=False)
    db.commit()
    return deleted


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def authenticate_user(db: Session, username: str, password: str) -> Usuario | None:
    normalized = username.strip().lower()
    user = db.query(Usuario).filter(Usuario.username == normalized, Usuario.activo == 1).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.ultimo_acceso = utc_now()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_session(db: Session, user_id: int) -> str:
    raw_token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user_id,
        token_hash=hash_session_token(raw_token),
        expires_at=utc_now() + timedelta(hours=SESSION_HOURS),
    )
    db.add(session)
    db.commit()
    return raw_token


def get_user_by_token(db: Session, raw_token: str | None) -> Usuario | None:
    if not raw_token:
        return None
    session = db.query(AuthSession).filter(AuthSession.token_hash == hash_session_token(raw_token)).first()
    if not session:
        return None
    now = utc_now()
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        db.delete(session)
        db.commit()
        return None
    user = db.query(Usuario).filter(Usuario.id == session.user_id, Usuario.activo == 1).first()
    if not user:
        db.delete(session)
        db.commit()
        return None
    return user


def delete_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    session = db.query(AuthSession).filter(AuthSession.token_hash == hash_session_token(raw_token)).first()
    if session:
        db.delete(session)
        db.commit()


def update_own_profile(db: Session, user: Usuario, username: str, nombre: str, password: str | None = None) -> Usuario:
    from app.core.security import hash_password

    normalized = username.strip().lower()
    display_name = nombre.strip()
    duplicate = db.query(Usuario).filter(Usuario.username == normalized, Usuario.id != user.id).first()
    if duplicate:
        raise ValueError('Ya existe otro usuario con ese nombre.')
    if not normalized or not display_name:
        raise ValueError('El usuario y el nombre son obligatorios.')
    antes = {'username': user.username, 'nombre': user.nombre}
    user.username = normalized
    user.nombre = display_name
    if password:
        user.password_hash = hash_password(password)
    db.add(user)
    add_audit(db, user.id, 'actualizacion', 'usuarios', user.id, antes, {'username': user.username, 'nombre': user.nombre})
    db.commit()
    db.refresh(user)
    return user
