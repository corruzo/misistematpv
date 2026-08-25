import asyncio
import hmac
import os
import secrets
import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import SQLAlchemyError
from app.controllers.employee_controller import router
from app.controllers.user_controller import router as user_router
from app.controllers.auth_controller import router as auth_router
from app.controllers.attendance_controller import router as attendance_router
from fastapi import Depends
from app.core.auth import require_user
from app.core.config import APP_ENV, COOKIE_SECURE, CSRF_ALLOWED_ORIGINS, SERIAL_PORT, STATIC_DIR
from app.database.session import SessionLocal
from app.services.auth_service import cleanup_expired_sessions
from app.services.serial_reader import SerialAttendanceReader

app = FastAPI(
    docs_url='/docs' if APP_ENV != 'production' else None,
    redoc_url=None,
    openapi_url='/openapi.json' if APP_ENV != 'production' else None,
)
_session_cleanup_task = None
_serial_reader = SerialAttendanceReader()


def validate_serial_worker_count(worker_count: int, serial_port: str) -> None:
    if serial_port and worker_count > 1:
        raise RuntimeError(
            'SERIAL_PORT requiere un solo worker. Configure WEB_CONCURRENCY=1 o deje SERIAL_PORT vacío.'
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

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.csp_nonce = secrets.token_urlsafe(16)
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('origin')
            if not origin or origin.rstrip('/') not in CSRF_ALLOWED_ORIGINS:
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
app.include_router(auth_router)
app.include_router(router, dependencies=[Depends(require_user)])
app.include_router(user_router, dependencies=[Depends(require_user)])
app.include_router(attendance_router, dependencies=[Depends(require_user)])
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


@app.on_event('startup')
def on_startup():
    global _session_cleanup_task
    validate_serial_worker_count(configured_worker_count(), SERIAL_PORT)
    _session_cleanup_task = asyncio.create_task(_session_cleanup_loop())
    _serial_reader.start()


async def _session_cleanup_loop():
    while True:
        db = SessionLocal()
        try:
            cleanup_expired_sessions(db)
        except SQLAlchemyError as exc:
            print(f'WARNING: No se pudieron limpiar sesiones expiradas: {exc}')
        finally:
            db.close()
        await asyncio.sleep(24 * 60 * 60)


@app.on_event('shutdown')
async def on_shutdown():
    if _session_cleanup_task:
        _session_cleanup_task.cancel()
    _serial_reader.stop()


if __name__ == '__main__':
    worker_count = configured_worker_count()
    validate_serial_worker_count(worker_count, SERIAL_PORT)
    uvicorn.run(
        'run:app',
        host=os.getenv('APP_HOST', '0.0.0.0'),
        port=int(os.getenv('APP_PORT', '8000')),
        reload=APP_ENV != 'production',
        workers=worker_count,
    )
