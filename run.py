from collections import defaultdict, deque
from time import monotonic

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
from app.core.config import CSRF_ALLOWED_ORIGINS
from app.database.session import SessionLocal
from app.services.organization_service import ensure_default_organization

app = FastAPI()

_auth_attempts = defaultdict(deque)
AUTH_RATE_WINDOW_SECONDS = 60
AUTH_RATE_LIMIT = 5


def client_key(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


def is_rate_limited(request: Request, scope: str) -> bool:
    now = monotonic()
    key = f'{scope}:{client_key(request)}'
    attempts = _auth_attempts[key]
    while attempts and now - attempts[0] >= AUTH_RATE_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= AUTH_RATE_LIMIT:
        return True
    attempts.append(now)
    return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') not in CSRF_ALLOWED_ORIGINS:
                return JSONResponse({'detail': 'Origen de solicitud no permitido.'}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
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


@app.middleware('http')
async def auth_rate_limit(request: Request, call_next):
    if request.method == 'POST' and request.url.path in {'/login', '/setup'}:
        if is_rate_limited(request, request.url.path):
            return JSONResponse({'detail': 'Demasiados intentos. Espera un minuto e inténtalo de nuevo.'}, status_code=429)
    return await call_next(request)


@app.on_event('startup')
def on_startup():
    db = SessionLocal()
    try:
        ensure_default_organization(db)
    except SQLAlchemyError as exc:
        print(f'WARNING: No se pudo inicializar la base de datos: {exc}')
        print('La aplicación seguirá disponible; reiníciala después de preparar SQL Server.')
    finally:
        db.close()


if __name__ == '__main__':
    uvicorn.run('run:app', host='127.0.0.1', port=8000, reload=True)
