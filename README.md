# MarcajeTPV

Aplicación web para gestión de empleados y organización empresarial con SQL Server.

## Guía del sistema

La referencia operativa y técnica está en [docs/GUIA_DEL_SISTEMA.md](docs/GUIA_DEL_SISTEMA.md). Incluye el mapa de pantallas, el flujo diario de asistencia, los roles actuales, las reglas de corrección y el procedimiento para documentar nuevas funciones.

Las funciones pendientes y las decisiones abiertas se mantienen en la sección correspondiente de [docs/GUIA_DEL_SISTEMA.md](docs/GUIA_DEL_SISTEMA.md). Las funciones solo se consideran terminadas cuando están implementadas y validadas.

## Requisitos previos

- Git instalado para clonar el repositorio.
- Python instalado y disponible como `python` en PowerShell o CMD.
- SQL Server con la base de datos disponible.
- SSMS (SQL Server Management Studio) o una herramienta equivalente para ejecutar el script inicial.
- ODBC Driver 17 para SQL Server instalado en la máquina.
- Windows (porque la app usa scripts .bat para iniciar el proyecto de forma rápida).

## Instalación desde GitHub en una PC nueva

Este es el procedimiento oficial para una PC que nunca ha ejecutado el sistema. Hazlo en este orden:

1. Instala Git, Python y el ODBC Driver 17 para SQL Server. Durante la instalación de Python activa `Add Python to PATH`.
2. Clona el repositorio y entra en su carpeta:

```powershell
git clone <URL-DEL-REPOSITORIO>
cd misistematpv
```

3. Inicia SQL Server y abre `scripts/create_database.sql` en SSMS. Ejecuta el script completo. Este script crea la base `misistema_db` y las tablas iniciales. Si SQL Server usa una instancia distinta, asegúrate de conectarte a esa instancia en SSMS.
4. Revisa el archivo `.env`. La primera ejecución crea ese archivo automáticamente desde `.env.template`. Por defecto `DB_SERVER=auto` prueba la instancia normal (`localhost`) y SQL Server Express (`localhost\SQLEXPRESS`). Si SQL Server está en otro equipo o usa otro nombre de instancia, cambia `DB_SERVER` por el servidor exacto. Con autenticación de Windows conserva `DB_TRUSTED=true` y deja `DB_USER` y `DB_PASSWORD` vacíos. El lector HID queda configurado por defecto en `COM1` a `9600` baudios; cambia `SERIAL_PORT` solo si el equipo usa otro puerto.
5. Desde la raíz del repositorio ejecuta:

```powershell
.\start_app.bat
```

El lanzador crea `.venv`, instala `requirements.txt`, aplica las migraciones Alembic pendientes y arranca la aplicación. En ejecuciones posteriores no tienes que repetir esos pasos.

6. Abre la dirección que muestra la consola. En la misma PC normalmente es `http://127.0.0.1:8000/`. Si es la primera instalación, entra en `/setup` para crear el primer usuario administrador; después usa `/login`.

### Producción

No uses la configuración `development` de la red LAN para producción. Define `APP_ENV=production`, `COOKIE_SECURE=true`, `TRUST_SERVER_CERTIFICATE=false`, `INITIAL_SETUP_ENABLED=false`, `KIOSK_ALLOWED_IPS` con las IP de las estaciones autorizadas y proporciona rutas existentes en `SSL_CERTFILE` y `SSL_KEYFILE`. La aplicación rechazará iniciar si falta TLS, una estación autorizada o si el certificado de SQL Server no se verifica.

Si la base de datos ya existía y solo estás instalando el código en otra PC, no vuelvas a crearla: configura el mismo `DB_SERVER` y `DB_NAME` en `.env` y ejecuta `start_app.bat` para aplicar las migraciones pendientes.

### Actualizar una instalación existente

Después de traer cambios desde GitHub:

```powershell
git pull
.\start_app.bat
```

El arranque aplica automáticamente las migraciones nuevas. Solo usa la actualización forzada de dependencias cuando cambien `requirements.txt` o `requirements-dev.txt`:

```powershell
.\start_app.bat /update
```

### Errores habituales al instalar

- `python no se reconoce`: reinstala Python activando `Add Python to PATH`, o usa `py start_app.py` como alternativa.
- Error de `ODBC Driver 17`: instala el Microsoft ODBC Driver 17 para SQL Server y reinicia la terminal.
- Error de conexión SQL Server: verifica que el servicio esté iniciado. Con instalación local deja `DB_SERVER=auto`; para una instancia remota configura `DB_SERVER=SERVIDOR\INSTANCIA` (o `SERVIDOR,PUERTO`) y revisa la autenticación.
- Error al abrir el puerto: cambia `APP_PORT` en `.env` y vuelve a ejecutar el lanzador. Para acceder desde otra PC, permite ese puerto en el firewall de Windows.
- No hay marcajes con lector: revisa el COM en el Administrador de dispositivos y configúralo en `SERIAL_PORT`; el lector debe enviar el código terminado en `CR` o `LF`.

## Copia portable del proyecto

Si vas a llevar una copia de la carpeta raíz a otra PC en lugar de clonar Git:

1. Copia toda la carpeta del proyecto.
2. En la PC nueva instala los mismos requisitos previos indicados arriba.
3. Si es una base de datos nueva, abre SSMS y ejecuta `scripts/create_database.sql` completo. Si reutilizas una base existente, conserva sus datos y configura su conexión en `.env`.
4. En la raíz del proyecto, ejecuta `.\start_app.bat` desde PowerShell o `start_app.bat` desde CMD.

Eso crea el entorno virtual si hace falta, instala las dependencias solo cuando no están disponibles, crea `.env` si no existe, aplica las migraciones y levanta la aplicación.

## Cómo funciona el arranque

El archivo `start_app.bat` hace lo siguiente automáticamente:

- Crea `.venv` si no existe
- Comprueba las dependencias instaladas y evita descargas innecesarias
- Permite actualizar dependencias explícitamente con `start_app.bat /update`
- Copia `.env.template` a `.env` si aún no hay uno
- Ejecuta la app con `python run.py`

El arranque normal usa una sola instancia estable y no activa la recarga automática. Para desarrollo con recarga, define `APP_RELOAD=true` en `.env`; no se recomienda en el equipo de producción o kiosco.

La dependencia frontend Bootstrap está inventariada en `frontend-dependencies.json` con versión e integridad SRI. Para actualizarla, fija una nueva versión, calcula los hashes SHA-384 de CSS y JS, actualiza el inventario y `app/templates/base.html`, y ejecuta `pytest` antes de desplegar.

## Variables de entorno

La configuración de conexión se toma de `.env`.

Ejemplo base:

```env
DB_SERVER=auto
DB_SERVER_CANDIDATES=localhost,localhost\SQLEXPRESS
DB_NAME=misistema_db
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_USER=
DB_PASSWORD=
DB_TRUSTED=true
APP_TIMEZONE=America/Caracas
SERIAL_PORT=
SERIAL_BAUDRATE=9600
SERIAL_BYTESIZE=8
SERIAL_PARITY=N
SERIAL_STOPBITS=1
SERIAL_TIMEOUT=1
SERIAL_ENCODING=ascii
```

Si usas autenticación de Windows, deja `DB_TRUSTED=true` y `DB_USER`/`DB_PASSWORD` vacíos. Con `DB_SERVER=auto`, la aplicación detecta automáticamente SQL Server normal o Express en el equipo local. Para otro equipo o una instancia con nombre diferente, usa el valor exacto de `DB_SERVER`.

Los marcajes se registran desde el kiosco y el formulario de registro manual. Los códigos de tarjeta existentes se conservan como datos del empleado y los marcajes históricos mantienen su origen para auditoría.

## Backups del sistema

El rol `Desarrollador` puede abrir `/system/backups`, crear una copia manual y descargar cualquiera de los tres slots disponibles. La aplicación crea automáticamente una copia cada 24 horas y rota `backup_1.bak`, `backup_2.bak` y `backup_3.bak` en la carpeta indicada por `BACKUP_DIR`.

La carpeta debe existir en el servidor y la cuenta del servicio de SQL Server debe tener permisos de escritura allí. El archivo `.bak` se genera en el servidor; el navegador solo recibe una descarga autorizada de un slot válido. Configura `BACKUP_DIR` con una ruta absoluta en producción si la aplicación y SQL Server usan directorios de trabajo distintos.

En Windows, concede a la cuenta del servicio de SQL Server permisos de modificación sobre `BACKUP_DIR`. Por ejemplo, para SQL Express:

```powershell
icacls C:\ruta\del\proyecto\app\backups /grant "NT Service\MSSQL`$SQLEXPRESS:(OI)(CI)(M)"
```

La aplicación ejecuta el backup con `autocommit`; no debe envolverse `BACKUP DATABASE` en una transacción SQL normal.

En desarrollo existe temporalmente `/attendance/simulator`, una pantalla protegida para probar el flujo del kiosco escribiendo un código de tarjeta. Esta ruta no se registra cuando `APP_ENV=production`.

## Arranque manual

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Para aplicar cambios de esquema en una instalación existente, ejecuta:

```bash
python -m alembic upgrade head
```

La migración crea `alembic_version`, ajusta la unicidad de departamentos y cargos al ámbito de su padre y crea `auditoria` y el registro persistente de alertas de acceso denegado. El script `scripts/create_database.sql` también incluye esas estructuras para instalaciones nuevas; los cambios posteriores deben quedar en una revisión Alembic.

Las pruebas portables se ejecutan localmente con:

```bash
python -m pytest --cov=app --cov-report=term-missing
```

GitHub Actions ejecuta automáticamente esta suite en cada push y pull request. Las pruebas que requieren SQL Server se mantienen separadas para ejecutarse contra una base configurada.

La app quedará disponible en la red local. El lanzador muestra la IP exacta del equipo al iniciar; el valor por defecto es:

```text
http://<IP-LOCAL-DEL-EQUIPO>:8000/
```

El servidor escucha en `0.0.0.0:8000`. Para iniciarlo en Windows ejecuta `start_app.bat` (o `python start_app.py`); desde otra PC abre la URL con la IP local mostrada en consola. En desarrollo, las solicitudes del mismo host permiten el flujo CSRF; en producción deben declararse explícitamente en `CSRF_ALLOWED_ORIGINS`.

## Módulo de usuarios

El sistema incluye tres roles: `Desarrollador` (gestión total y herramientas del sistema), `RRHH` (empleados y asistencia) e `Inspector` (consulta operativa y marcaje manual autorizado). Antes de usar la pantalla de usuarios, aplica las migraciones pendientes con `python -m alembic upgrade head`.

Después, abre:

```text
http://127.0.0.1:8000/users
```

Las contraseñas no se guardan en texto plano: se almacenan usando `scrypt` con parámetros versionados en el hash. La interfaz permite crear usuarios, asignar roles, listarlos y activar o inhabilitar cuentas. El primer usuario creado por `/setup` es `Desarrollador`.

## Inicio de sesión y perfil

La aplicación ahora requiere autenticación para el dashboard, empleados, estructura y administración de usuarios. Ejecuta nuevamente `scripts/create_database.sql` para crear también `sesiones_usuario`; esta tabla guarda únicamente hashes de sesiones, nunca las cookies en texto plano.

- Login: `http://<IP-LOCAL-DEL-EQUIPO>:8000/login`
- Configuración inicial: `http://<IP-LOCAL-DEL-EQUIPO>:8000/setup` mientras no exista ningún usuario.
- Perfil propio: disponible desde el nombre del usuario en el header o en `/profile`.
- Cierre de sesión: botón `Cerrar sesión` en el header.

Las sesiones duran 12 horas y usan cookie `HttpOnly` y `SameSite=Lax`, adecuadas para el turno completo de los inspectores. Las operaciones mutables validan el origen, las rutas API declaran sus dependencias de autorización y las respuestas usan CSP con nonce. En producción con HTTPS, activa `Secure` para la cookie.

La hora se almacena internamente en UTC y se muestra en la zona definida por `APP_TIMEZONE`. El valor recomendado para esta instalación es `America/Caracas` (UTC-04:00). Después de cambiar esta variable, reinicia la aplicación.

Las altas, modificaciones, bajas, cambios de estado y marcajes manuales se registran en `auditoria` con usuario, entidad, fecha y JSON anterior/posterior. Un proceso de mantenimiento elimina sesiones expiradas una vez al día; en despliegues con varios workers conviene mover esta tarea a SQL Server Agent.

Las búsquedas usan `LIKE`, aprovechando la collation case-insensitive de SQL Server configurada normalmente. Si la instalación utiliza una collation case-sensitive, debe revisarse antes de desplegar el cambio.

## Mejoras recomendadas

1. Incorporar auditoría de altas, cambios de estado y accesos.
2. Añadir recuperación y cambio de contraseña con política de caducidad.
3. Ampliar pruebas automatizadas de API, reglas jerárquicas y validación de archivos.
4. Mover el rate limiting a SQL Server o un backend compartido al desplegar varios workers.
5. Configurar logs estructurados sin contraseñas, tokens ni datos sensibles.
6. Añadir migraciones versionadas para cambios de esquema futuros.
7. Servir recursos frontend con versiones fijadas y retirar gradualmente `style-src 'unsafe-inline'`.

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
