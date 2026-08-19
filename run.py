import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import SQLAlchemyError
from app.controllers.employee_controller import router
from app.controllers.user_controller import router as user_router
from app.controllers.auth_controller import router as auth_router
from fastapi import Depends
from app.core.auth import require_user
from app.database.session import SessionLocal
from app.services.organization_service import ensure_default_organization

app = FastAPI()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.include_router(auth_router)
app.include_router(router, dependencies=[Depends(require_user)])
app.include_router(user_router, dependencies=[Depends(require_user)])
app.mount('/static', StaticFiles(directory='app/static'), name='static')


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
