import asyncio
import secrets

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
from app.core.config import APP_ENV, CSRF_ALLOWED_ORIGINS
from app.core.rate_limit import is_rate_limited
from app.database.session import SessionLocal
from app.services.organization_service import ensure_default_organization
from app.services.auth_service import cleanup_expired_sessions

app = FastAPI(
    docs_url='/docs' if APP_ENV != 'production' else None,
    redoc_url=None,
    openapi_url='/openapi.json' if APP_ENV != 'production' else None,
)
_session_cleanup_task = None

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.csp_nonce = secrets.token_urlsafe(16)
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') not in CSRF_ALLOWED_ORIGINS:
                return JSONResponse({'detail': 'Origen de solicitud no permitido.'}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Content-Security-Policy', f"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'nonce-{request.state.csp_nonce}' https://cdn.jsdelivr.net; connect-src 'self' https://cdn.jsdelivr.net; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        if request.url.scheme == 'https':
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.include_router(auth_router)
app.include_router(router, dependencies=[Depends(require_user)])
app.include_router(user_router, dependencies=[Depends(require_user)])
app.include_router(attendance_router, dependencies=[Depends(require_user)])
app.mount('/static', StaticFiles(directory='app/static'), name='static')


@app.on_event('startup')
def on_startup():
    global _session_cleanup_task
    db = SessionLocal()
    try:
        ensure_default_organization(db)
    except SQLAlchemyError as exc:
        print(f'WARNING: No se pudo inicializar la base de datos: {exc}')
        print('La aplicación seguirá disponible; reiníciala después de preparar SQL Server.')
    finally:
        db.close()
    _session_cleanup_task = asyncio.create_task(_session_cleanup_loop())


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


if __name__ == '__main__':
    uvicorn.run('run:app', host='127.0.0.1', port=8000, reload=APP_ENV != 'production')
