# MarcajeTPV

Aplicación web para gestión de empleados y organización empresarial con SQL Server.

## Requisitos previos

- SQL Server con la base de datos disponible.
- ODBC Driver 17 para SQL Server instalado en la máquina.
- Windows (porque la app usa scripts .bat para iniciar el proyecto de forma rápida).

## Copia portable del proyecto

Si vas a llevar la carpeta raíz a otra PC:

1. Copia toda la carpeta del proyecto.
2. Abre SSMS y ejecuta el script SQL de creación/actualización de la base de datos.
3. En la raíz del proyecto, ejecuta el archivo:
   - `start_app.bat`

Eso crea el entorno virtual si hace falta, instala las dependencias desde `requirements.txt`, crea `.env` si no existe y levanta la aplicación.

## Cómo funciona el arranque

El archivo `start_app.bat` hace lo siguiente automáticamente:

- Crea `.venv` si no existe
- Instala dependencias con `pip install -r requirements.txt`
- Copia `.env.example` a `.env` si aún no hay uno
- Ejecuta la app con `python run.py`

## Variables de entorno

La configuración de conexión se toma de `.env`.

Ejemplo base:

```env
DB_SERVER=localhost
DB_NAME=misistema_db
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_USER=
DB_PASSWORD=
DB_TRUSTED=true
```

Si usas autenticación de Windows, deja `DB_TRUSTED=true` y `DB_USER`/`DB_PASSWORD` vacíos.

## Arranque manual

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

La app quedará disponible en:

```text
http://127.0.0.1:8000/
```

## Módulo de usuarios

La primera versión incluye un único rol: `Administrador`. Antes de usar la pantalla de usuarios, ejecuta nuevamente `scripts/create_database.sql` en SSMS para crear la tabla `usuarios` de forma idempotente.

Después, abre:

```text
http://127.0.0.1:8000/users
```

Las contraseñas no se guardan en texto plano: se almacenan usando `scrypt`. La interfaz permite crear usuarios, listarlos y activar o inhabilitar cuentas. El rol inicial disponible es `Administrador`.

## Inicio de sesión y perfil

La aplicación ahora requiere autenticación para el dashboard, empleados, estructura y administración de usuarios. Ejecuta nuevamente `scripts/create_database.sql` para crear también `sesiones_usuario`; esta tabla guarda únicamente hashes de sesiones, nunca las cookies en texto plano.

- Login: `http://127.0.0.1:8000/login`
- Configuración inicial: `http://127.0.0.1:8000/setup` mientras no exista ningún usuario.
- Perfil propio: disponible desde el nombre del usuario en el header o en `/profile`.
- Cierre de sesión: botón `Cerrar sesión` en el header.

Las sesiones duran 8 horas y usan cookie `HttpOnly` y `SameSite=Lax`. En producción con HTTPS, activa `Secure` para la cookie y añade autenticación/autorización formal antes de exponer el servicio fuera de la máquina local.

## Mejoras recomendadas

1. Implementar inicio de sesión con sesiones seguras y expiración.
2. Añadir protección CSRF para operaciones que cambian datos.
3. Aplicar autorización por permisos antes de exponer la aplicación fuera de `127.0.0.1`.
4. Incorporar auditoría de altas, cambios de estado y accesos.
5. Añadir recuperación y cambio de contraseña con política de caducidad.
6. Crear pruebas automatizadas de API, reglas jerárquicas y validación de archivos.
7. Añadir rate limiting para endpoints de autenticación y operaciones sensibles.
8. Configurar logs estructurados sin contraseñas, tokens ni datos sensibles.
9. Añadir migraciones versionadas para cambios de esquema futuros.
10. Servir recursos frontend con versiones fijadas y una CSP progresiva.

## Ejecutable o arranque directo

La opción más práctica para mover la carpeta raíz a otra PC es usar el archivo `start_app.bat`, que crea el entorno virtual y levanta la aplicación sin pasos manuales extra.

Si además quieres generar un `.exe` en una máquina con acceso a internet, usa:

```bash
.venv\Scripts\activate
python -m pip install pyinstaller
pyinstaller --onefile --name MarcajeTPV run.py
```

El ejecutable se genera en la carpeta `dist`.

> Importante: en el equipo destino sigue siendo necesario tener instalado el ODBC Driver 17 para SQL Server.
