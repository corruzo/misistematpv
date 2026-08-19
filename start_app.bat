@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv" (
    echo Creando entorno virtual...
    python -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist ".env" (
    echo Creando archivo .env desde plantilla...
    copy .env.template .env
)

python run.py
