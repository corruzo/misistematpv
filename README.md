# MarcajeTPV

Aplicación web para gestión de empleados y organización empresarial con SQL Server.

## Guía del sistema

La referencia operativa y técnica está en [docs/GUIA_DEL_SISTEMA.md](docs/GUIA_DEL_SISTEMA.md). Incluye el mapa de pantallas, el flujo diario de asistencia, los roles actuales, las reglas de corrección y el procedimiento para documentar nuevas funciones.

El archivo [prioridades_inspector_garita.md](prioridades_inspector_garita.md) conserva el checklist de producto. Las casillas solo deben marcarse cuando la función esté implementada y validada; las decisiones o pendientes deben explicarse en la guía central.

## Requisitos previos

- SQL Server con la base de datos disponible.
- ODBC Driver 17 para SQL Server instalado en la máquina.
- Windows (porque la app usa scripts .bat para iniciar el proyecto de forma rápida).

## Copia portable del proyecto

Si vas a llevar la carpeta raíz a otra PC:

1. Copia toda la carpeta del proyecto.
2. Abre SSMS y ejecuta el script SQL de creación/actualización de la base de datos, incluida la tabla de alertas de acceso denegado.
3. En la raíz del proyecto, ejecuta el archivo:
   - `start_app.bat`

Eso crea el entorno virtual si hace falta, instala las dependencias solo cuando no están disponibles, crea `.env` si no existe y levanta la aplicación. Si ya está preparado, el arranque no descarga nada.

Para forzar una actualización de dependencias:

```bat
start_app.bat /update
```

## Cómo funciona el arranque

El archivo `start_app.bat` hace lo siguiente automáticamente:

- Crea `.venv` si no existe
- Comprueba las dependencias instaladas y evita descargas innecesarias
- Permite actualizar dependencias explícitamente con `start_app.bat /update`
- Copia `.env.template` a `.env` si aún no hay uno
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
APP_TIMEZONE=America/Caracas
SERIAL_PORT=
SERIAL_BAUDRATE=9600
SERIAL_BYTESIZE=8
SERIAL_PARITY=N
SERIAL_STOPBITS=1
SERIAL_TIMEOUT=1
SERIAL_ENCODING=ascii
```

Si usas autenticación de Windows, deja `DB_TRUSTED=true` y `DB_USER`/`DB_PASSWORD` vacíos.

Para el lector serial, configura `SERIAL_PORT` con el COM asignado por Windows. En equipos de desarrollo sin lector, deja `SERIAL_PORT=` vacío: la aplicación funciona normalmente y no intenta abrir ningún puerto. En la PC de producción, conecta el lector, revisa el COM en el Administrador de dispositivos y configura ese valor, por ejemplo `SERIAL_PORT=COM5`. La configuración inicial usa 9600 baudios, 8 bits, sin paridad y 1 bit de parada (8N1); cambia `SERIAL_PARITY` a `E` u `O`, o `SERIAL_STOPBITS`, si el fabricante indica otros valores. El lector debe enviar el código de tarjeta terminado en salto de línea (`CR` o `LF`).

El lector RFID funciona mediante el agente independiente de `rfid_agent`. En la PC de la garita, copia `rfid_agent.env.example` a `rfid_agent.env`, configura `PUERTO_COM`, `URL_SERVIDOR`, `GARITA_ID` y `API_KEY`, y ejecuta `install_rfid_agent.ps1` como administrador. El servicio arranca automáticamente con Windows y conserva lecturas en SQLite si el servidor no está disponible.

El servidor web ya no abre puertos COM ni necesita un worker único por lector. `POST /api/v1/asistencia/lectura` usa Bearer API key y `timestamp_lectura`; el navegador solo recibe el resultado mediante SSE para visualización.

## Backups del sistema

El rol `Sistemas` (y `Administrador` como respaldo) puede abrir `/system/backups`, crear una copia manual y descargar cualquiera de los tres slots disponibles. La aplicación crea automáticamente una copia cada 24 horas y rota `backup_1.bak`, `backup_2.bak` y `backup_3.bak` en la carpeta indicada por `BACKUP_DIR`.

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

El sistema incluye cuatro roles: `Administrador` (gestión total), `RRHH` (empleados y reportes), `Consulta` (solo lectura) y `Sistemas` (herramientas de sistema y backups). Antes de usar la pantalla de usuarios, ejecuta nuevamente `scripts/create_database.sql` en SSMS para crear o actualizar las tablas de forma idempotente.

Después, abre:

```text
http://127.0.0.1:8000/users
```

Las contraseñas no se guardan en texto plano: se almacenan usando `scrypt` con parámetros versionados en el hash. La interfaz permite crear usuarios, asignar roles, listarlos y activar o inhabilitar cuentas. El primer usuario creado por `/setup` es `Administrador`.

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
