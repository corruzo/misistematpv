#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil

def run_cmd(args, env=None):
    """Ejecuta un comando y devuelve el código de salida."""
    try:
        result = subprocess.run(args, env=env, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error al ejecutar {' '.join(args)}: {e}")
        return 1

def main():
    print("=========================================")
    print("   Gestor de Arranque de MarcajeTPV      ")
    print("=========================================")
    
    # 1. Ajustar el directorio de trabajo al directorio del script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir:
        os.chdir(base_dir)
    else:
        base_dir = os.getcwd()
    
    # 2. Rutas del entorno virtual
    venv_dir = os.path.join(base_dir, ".venv")
    if os.name == "nt":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")
        
    # 3. Crear entorno virtual si no existe o si se solicita actualización
    force_update = "/update" in sys.argv or "--update" in sys.argv
    if not os.path.exists(venv_dir):
        print("Creando entorno virtual (.venv)...")
        if run_cmd([sys.executable, "-m", "venv", ".venv"]) != 0:
            print("ERROR: No se pudo crear el entorno virtual.")
            input("Presiona Enter para salir...")
            sys.exit(1)
        install_deps = True
    else:
        install_deps = force_update
        
    # Usar el python de .venv si existe, de lo contrario usar el actual
    active_python = venv_python if os.path.exists(venv_python) else sys.executable
    
    # 4. Comprobar e instalar dependencias si es necesario
    if not install_deps:
        # Intento rápido de importación para verificar si están las dependencias
        check_code = (
            "import fastapi, uvicorn, sqlalchemy, alembic, pyodbc, dotenv, jinja2, "
            "multipart, aiofiles, importlib.metadata as metadata; metadata.version('tzdata')"
        )
        if run_cmd([active_python, "-c", check_code]) != 0:
            install_deps = True

    if install_deps:
        print("Instalando o actualizando dependencias...")
        if run_cmd([active_python, "-m", "pip", "install", "-r", "requirements.txt"]) != 0:
            print("ERROR: No se pudieron instalar las dependencias.")
            input("Presiona Enter para salir...")
            sys.exit(1)
    else:
        print("Dependencias ya instaladas. Se omite la descarga.")
        
    # 5. Crear archivo .env desde plantilla si no existe
    env_file = os.path.join(base_dir, ".env")
    env_template = os.path.join(base_dir, ".env.template")
    if not os.path.exists(env_file):
        if os.path.exists(env_template):
            print("Creando archivo .env desde plantilla...")
            shutil.copyfile(env_template, env_file)
        else:
            print("WARNING: No se encontró .env.template para inicializar .env.")
            
    # 6. Aplicar migraciones de la base de datos automáticamente
    print("Aplicando migraciones de base de datos (Alembic)...")
    if run_cmd([active_python, "-m", "alembic", "upgrade", "head"]) != 0:
        print("\nWARNING: No se pudieron aplicar las migraciones automáticamente.")
        print("Asegúrate de que el servidor de SQL Server esté activo y de que")
        print("las credenciales en el archivo .env sean correctas.")
        
    # 7. Ejecutar la aplicación principal
    print("Iniciando MarcajeTPV...")
    try:
        result = subprocess.run([active_python, "run.py"])
        if result.returncode != 0:
            print(f"\nLa aplicación terminó con código de error {result.returncode}.")
            input("Presiona Enter para continuar...")
    except KeyboardInterrupt:
        print("\nAplicación detenida por el usuario.")
    except Exception as e:
        print(f"\nERROR al iniciar la aplicación: {e}")
        input("Presiona Enter para continuar...")

if __name__ == "__main__":
    main()
