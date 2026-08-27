from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import STATIC_DIR
from app.core.config import COOKIE_SECURE
from app.database.session import get_db
from app.services.auth_service import SESSION_COOKIE, SESSION_HOURS, acquire_initial_setup_lock, authenticate_user, create_session, delete_session
from app.services.user_service import create_user
from app.schemas.user import UsuarioCreate
from app.models.user import Usuario
from app.core.auth import current_user_optional
from app.core.rate_limit import is_rate_limited

router = APIRouter()
templates_env = Environment(
    loader=FileSystemLoader(str(STATIC_DIR.parent / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
)


@router.get('/')
def root_page(request: Request, user=Depends(current_user_optional)):
    if not user:
        return RedirectResponse('/login', status_code=303)
    return RedirectResponse('/attendance/summary', status_code=303)


@router.get('/login', response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    from app.services.auth_service import get_user_by_token
    if get_user_by_token(db, request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse('/', status_code=303)
    template = templates_env.get_template('login.html')
    error = 'Tu sesión expiró. Inicia sesión nuevamente.' if request.query_params.get('reason') == 'session_expired' else None
    return HTMLResponse(template.render(error=error))


@router.get('/setup', response_class=HTMLResponse)
def setup_page(db: Session = Depends(get_db)):
    template = templates_env.get_template('setup.html')
    try:
        has_users = db.query(Usuario).count()
    except SQLAlchemyError:
        db.rollback()
        return HTMLResponse(
            template.render(error='No se puede acceder a SQL Server. Ejecuta scripts/create_database.sql y revisa el archivo .env.', form_available=False),
            status_code=503,
        )
    if has_users:
        return HTMLResponse(
            template.render(error='La configuración inicial ya fue completada. Inicia sesión para administrar los usuarios.', form_available=False),
            status_code=409,
        )
    return HTMLResponse(template.render(error=None, form_available=True))


@router.post('/setup')
def setup_admin(
    request: Request,
    username: str = Form(..., min_length=3, max_length=50),
    nombre: str = Form(..., min_length=2, max_length=150),
    password: str = Form(..., min_length=10, max_length=128),
    db: Session = Depends(get_db),
):
    template = templates_env.get_template('setup.html')
    client_host = request.client.host if request.client else 'unknown'
    if is_rate_limited('/setup', client_host, username):
        return HTMLResponse(template.render(error='Demasiados intentos. Espera un minuto e inténtalo de nuevo.'), status_code=429)
    try:
        acquire_initial_setup_lock(db)
        has_users = db.query(Usuario).count()
    except SQLAlchemyError:
        db.rollback()
        return HTMLResponse(
            template.render(error='No se puede acceder a SQL Server. Ejecuta scripts/create_database.sql y revisa el archivo .env.', form_available=False),
            status_code=503,
        )
    except RuntimeError:
        db.rollback()
        return HTMLResponse(template.render(error='No se pudo bloquear la configuración inicial. Inténtalo nuevamente.'), status_code=503)
    if has_users:
        return HTMLResponse(
            template.render(error='La configuración inicial ya fue completada. Inicia sesión para administrar los usuarios.', form_available=False),
            status_code=409,
        )
    try:
        create_user(db, UsuarioCreate(username=username, nombre=nombre, password=password, rol='Desarrollador'))
    except Exception:
        db.rollback()
        return HTMLResponse(template.render(error='No se pudo crear el administrador.'), status_code=400)
    return RedirectResponse('/login', status_code=303)


@router.post('/login')
def login(
    request: Request,
    username: str = Form(..., min_length=3, max_length=50),
    password: str = Form(..., min_length=1, max_length=128),
    db: Session = Depends(get_db),
):
    client_host = request.client.host if request.client else 'unknown'
    if is_rate_limited('/login', client_host, username):
        template = templates_env.get_template('login.html')
        return HTMLResponse(template.render(error='Demasiados intentos. Espera un minuto e inténtalo de nuevo.'), status_code=429)
    if not username.strip() or not password:
        template = templates_env.get_template('login.html')
        return HTMLResponse(template.render(error='Escribe tu usuario y contraseña.'), status_code=400)
    try:
        user = authenticate_user(db, username, password)
    except SQLAlchemyError:
        db.rollback()
        template = templates_env.get_template('login.html')
        return HTMLResponse(template.render(error='No se pudo validar el acceso. Inténtalo nuevamente.'), status_code=503)
    if not user:
        template = templates_env.get_template('login.html')
        return HTMLResponse(template.render(error='Usuario o contraseña incorrectos.'), status_code=401)
    response = RedirectResponse('/', status_code=303)
    try:
        token = create_session(db, user.id)
    except SQLAlchemyError:
        db.rollback()
        template = templates_env.get_template('login.html')
        return HTMLResponse(template.render(error='No se pudo iniciar la sesión. Inténtalo nuevamente.'), status_code=503)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_HOURS * 60 * 60,
        httponly=True,
        samesite='lax',
        secure=COOKIE_SECURE,
        path='/',
    )
    return response


@router.post('/logout')
def logout(request: Request, db: Session = Depends(get_db)):
    try:
        delete_session(db, request.cookies.get(SESSION_COOKIE))
    except SQLAlchemyError:
        db.rollback()
    response = RedirectResponse('/login', status_code=303)
    response.delete_cookie(SESSION_COOKIE, path='/')
    return response
