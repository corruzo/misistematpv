import os
import sys
import subprocess
import shutil
import time
import urllib.error
import urllib.request
import webbrowser

def run_cmd(args, env=None):
    """Ejecuta un comando y devuelve el código de salida."""
    try:
        result = subprocess.run(args, env=env, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error al ejecutar {' '.join(args)}: {e}")
        return 1

def wait_for_server(url, process, timeout=30):
    """Espera a que Uvicorn acepte conexiones o a que el proceso termine."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return 200 <= response.status < 500
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    return False

def main():
    print("=========================================")
    print("   Gestor de Arranque de MarcajeTPV      ")
    print("=========================================")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir:
        os.chdir(base_dir)
    else:
        base_dir = os.getcwd()
    
    venv_dir = os.path.join(base_dir, ".venv")
    if os.name == "nt":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")
        
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
        
    active_python = venv_python if os.path.exists(venv_python) else sys.executable
    
    if not install_deps:
        check_code = (
            "import fastapi, uvicorn, sqlalchemy, alembic, pyodbc, dotenv, jinja2, "
            "multipart, aiofiles, serial, importlib.metadata as metadata; metadata.version('tzdata')"
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
        
    env_file = os.path.join(base_dir, ".env")
    env_template = os.path.join(base_dir, ".env.template")
    if not os.path.exists(env_file):
        if os.path.exists(env_template):
            print("Creando archivo .env desde plantilla...")
            shutil.copyfile(env_template, env_file)
        else:
            print("WARNING: No se encontró .env.template para inicializar .env.")
            
    print("Aplicando migraciones de base de datos (Alembic)...")
    if run_cmd([active_python, "-m", "alembic", "upgrade", "head"]) != 0:
        print("\nERROR: No se pudieron aplicar las migraciones automáticamente.")
        print("Asegúrate de que el servidor de SQL Server esté activo y de que")
        print("las credenciales en el archivo .env sean correctas.")
        input("Presiona Enter para salir...")
        sys.exit(1)
        
    port = os.getenv('APP_PORT', '8000')
    app_url = f"http://127.0.0.1:{port}/"
    print(f"Iniciando MarcajeTPV en {app_url}...")
    try:
        process = subprocess.Popen([active_python, "run.py"], env=os.environ.copy())
        if not wait_for_server(app_url, process):
            return_code = process.poll()
            if return_code is None:
                process.terminate()
                print("\nERROR: El servidor no respondió en 30 segundos.")
            else:
                print(f"\nLa aplicación terminó con código de error {return_code}.")
            input("Presiona Enter para continuar...")
            return
        print(f"Sistema listo: {app_url}")
        if "--no-browser" not in sys.argv:
            webbrowser.open(app_url)
        process.wait()
        if process.returncode != 0:
            print(f"\nLa aplicación terminó con código de error {process.returncode}.")
            input("Presiona Enter para continuar...")
    except KeyboardInterrupt:
        print("\nAplicación detenida por el usuario.")
    except Exception as e:
        print(f"\nERROR al iniciar la aplicación: {e}")
        input("Presiona Enter para continuar...")

if __name__ == "__main__":
    main()
