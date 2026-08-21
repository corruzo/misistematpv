@echo off
setlocal

cd /d "%~dp0"

set "INSTALL_DEPS=0"

if not exist ".venv" (
    echo Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    set "INSTALL_DEPS=1"
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: No se pudo activar el entorno virtual.
    pause
    exit /b 1
)

if /I "%~1"=="/update" (
    set "INSTALL_DEPS=1"
)

if "%INSTALL_DEPS%"=="0" (
    python -c "import fastapi, uvicorn, sqlalchemy, alembic, pyodbc, dotenv, jinja2, multipart, aiofiles, importlib.metadata as metadata; metadata.version('tzdata')" >nul 2>&1
    if errorlevel 1 set "INSTALL_DEPS=1"
)

if "%INSTALL_DEPS%"=="1" (
    echo Instalando o actualizando dependencias...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
) else (
    echo Dependencias ya instaladas. Se omite la descarga.
)

if not exist ".env" (
    echo Creando archivo .env desde plantilla...
    copy .env.template .env
)

echo Iniciando MarcajeTPV...
python run.py
