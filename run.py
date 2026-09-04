import asyncio
import hmac
import logging
import os
import secrets
import sys
import warnings
from contextlib import asynccontextmanager

import uvicorn
from sqlalchemy.exc import SAWarning
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.controllers.employee_controller import router
from app.controllers.organization_controller import router as organization_router
from app.controllers.user_controller import router as user_router
from app.controllers.auth_controller import router as auth_router
from app.controllers.attendance_controller import router as attendance_router
from app.controllers.system_controller import router as system_router, backup_loop
from app.controllers.notification_controller import router as notification_router
from fastapi import Depends
from app.core.auth import require_user
from app.core.config import APP_ENV, APP_RELOAD, COOKIE_SECURE, SERIAL_PORT, SSL_CERTFILE, SSL_KEYFILE, TEMPORARY_DATA_RETENTION_DAYS, asset_fingerprint, is_allowed_csrf_origin, STATIC_DIR
from app.core.exceptions import AppException
from app.database.session import SessionLocal
from app.services.auth_service import cleanup_expired_sessions
from app.services.notification_service import cleanup_temporary_data
from app.schemas.attendance import AttendanceOrigin
from app.services.attendance_service import AttendanceError, EmployeeAccessDeniedError, register_scan
from app.services.access_event_service import record_denied_event
from app.services.rfid_reader_service import get_reader

warnings.filterwarnings(
    'ignore',
    category=SAWarning,
    message=r'Unrecognized server version info .*',
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('websockets.server').setLevel(logging.WARNING)
logging.getLogger('websockets.client').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app):
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT 1'))
    except SQLAlchemyError as exc:
        raise RuntimeError('No se pudo verificar la conexión con la base de datos al iniciar.') from exc

    def process_reader_scan(card_code):
        with SessionLocal() as reader_db:
            try:
                register_scan(reader_db, card_code, AttendanceOrigin.PUERTO_COM)
            except EmployeeAccessDeniedError as exc:
                record_denied_event(reader_db, exc)
            except AttendanceError as exc:
                logger.info('Lectura HID no registrada: %s', exc)

    rfid_reader = get_reader()
    rfid_reader._on_attendance_scan = process_reader_scan
    rfid_reader.start()
    tasks = [
        asyncio.create_task(_session_cleanup_loop()),
        asyncio.create_task(backup_loop()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        rfid_reader.stop()


app = FastAPI(
    docs_url='/docs' if APP_ENV != 'production' else None,
    redoc_url=None,
    openapi_url='/openapi.json' if APP_ENV != 'production' else None,
    lifespan=lifespan,
)


def configured_worker_count(argv=None, environ=None) -> int:
    args = list(sys.argv if argv is None else argv)
    environment = os.environ if environ is None else environ
    for index, argument in enumerate(args):
        if argument == '--workers' and index + 1 < len(args):
            return int(args[index + 1])
        if argument.startswith('--workers='):
            return int(argument.split('=', 1)[1])
    return int(environment.get('WEB_CONCURRENCY', '1'))


def resolve_worker_count(argv=None, environ=None, serial_port: str | None = None) -> int:
    worker_count = configured_worker_count(argv, environ)
    if serial_port is None:
        serial_target = (SERIAL_PORT or '').strip()
    else:
        serial_target = serial_port.strip()
    if serial_target and worker_count != 1:
        return 1
    return worker_count

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.csp_nonce = secrets.token_urlsafe(16)
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('origin')
            if not origin or not is_allowed_csrf_origin(origin, request.headers.get('host', '')):
                return JSONResponse({'detail': 'Origen de solicitud no permitido.'}, status_code=403)
            if request.url.path.startswith('/api/'):
                cookie_token = request.cookies.get('csrftoken')
                header_token = request.headers.get('X-CSRFToken')
                if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
                    return JSONResponse({'detail': 'Token de seguridad inválido o ausente.'}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Content-Security-Policy', f"default-src 'self'; img-src 'self' data:; style-src 'self' 'nonce-{request.state.csp_nonce}' https://cdn.jsdelivr.net; script-src 'self' 'nonce-{request.state.csp_nonce}' https://cdn.jsdelivr.net; connect-src 'self' https://cdn.jsdelivr.net; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        if 'csrftoken' not in request.cookies:
            response.set_cookie(
                'csrftoken',
                secrets.token_urlsafe(32),
                httponly=False,
                secure=COOKIE_SECURE,
                samesite='lax',
                path='/',
            )
        if request.url.scheme == 'https':
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response


app.add_middleware(SecurityHeadersMiddleware)

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    if request.url.path.startswith('/api/'):
        content = {'detail': exc.message}
        if exc.details:
            content['details'] = exc.details
        return JSONResponse(content, status_code=exc.status_code)
    return JSONResponse({'detail': exc.message}, status_code=exc.status_code)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception('Error de SQLAlchemy en endpoint %s', request.url.path)
    if request.url.path.startswith('/api/'):
        return JSONResponse({'detail': 'Error de comunicación o consulta en la base de datos SQL Server.'}, status_code=500)
    return JSONResponse({'detail': 'Error al procesar la solicitud en la base de datos.'}, status_code=500)


@app.get('/healthz', include_in_schema=False)
def health_check():
    return {'status': 'ok'}


app.include_router(auth_router)
app.include_router(router, dependencies=[Depends(require_user)])
app.include_router(organization_router, dependencies=[Depends(require_user)])
app.include_router(user_router, dependencies=[Depends(require_user)])
app.include_router(attendance_router, dependencies=[Depends(require_user)])
app.include_router(system_router, dependencies=[Depends(require_user)])
app.include_router(notification_router)
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


@app.get('/favicon.ico', include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / 'img' / 'favicon.svg', media_type='image/svg+xml')


async def _session_cleanup_loop():
    while True:
        db = SessionLocal()
        try:
            cleanup_expired_sessions(db)
            result = cleanup_temporary_data(db, TEMPORARY_DATA_RETENTION_DAYS)
            if any(result.values()):
                logger.info('Purga temporal ejecutada: %s', result)
        except SQLAlchemyError as exc:
            logger.warning('No se pudieron limpiar sesiones expiradas: %s', exc)
        finally:
            db.close()
        await asyncio.sleep(24 * 60 * 60)

if __name__ == '__main__':
    worker_count = resolve_worker_count(serial_port=SERIAL_PORT)
    if SERIAL_PORT and worker_count == 1:
        logger.warning('El lector HID usa %s; se forzará un solo worker para evitar competencia por el puerto.', SERIAL_PORT)
    uvicorn.run(
        'run:app',
        host=os.getenv('APP_HOST', '0.0.0.0'),
        port=int(os.getenv('APP_PORT', '8000')),
        reload=APP_RELOAD,
        workers=worker_count,
        access_log=False,
        ssl_certfile=SSL_CERTFILE or None,
        ssl_keyfile=SSL_KEYFILE or None,
    )
