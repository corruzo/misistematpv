# Guía del sistema MarcajeTPV

Documento de referencia para entender, operar y mantener MarcajeTPV sin depender de memoria informal.

## 1. Qué resuelve

MarcajeTPV gestiona:

- Empleados y su estructura organizativa.
- Usuarios, roles y sesiones.
- Marcajes de asistencia desde lector RFID, kiosco y registro manual.
- Historial, resumen operativo y correcciones auditadas.
- Backups administrados desde el módulo de Sistemas.

La aplicación usa FastAPI, plantillas Jinja2, JavaScript del navegador y SQL Server mediante SQLAlchemy.

## 2. Mapa rápido de la aplicación

| Necesidad | Pantalla | Ruta principal | Autorización |
| --- | --- | --- | --- |
| Resumen operativo de asistencia | Resumen | `/attendance/summary` | Usuario autenticado |
| Registrar marcaje manual | Marcaje manual rápido | `/attendance` | Administrador o RRHH |
| Consultar y corregir marcajes | Historial | `/attendance/history` | Usuario con lectura; corrección para Administrador o RRHH |
| Operar el lector en pantalla completa | Kiosco | `/attendance/kiosk` | Usuario autenticado |
| Gestionar empleados | Gestión de personal | `/employees` | Administrador o RRHH |
| Administrar usuarios | Gestión de usuarios | `/users` | Administrador |
| Organigrama | Organigrama TPV | `/organization` | Administrador |
| Backups y sistema | Sistema y backups | `/system/backups` | Administrador o Sistemas |

## 3. Flujo diario de asistencia

### Inicio del turno

1. Iniciar la aplicación con `start_app.bat`.
2. Confirmar que el estado de la base de datos aparece conectado.
3. Abrir `Resumen` y revisar personas dentro, movimientos recientes, personal sin marcaje y alertas.
4. Confirmar el estado del lector RFID antes de depender del marcaje automático.

### Marcaje automático

El lector envía el código de tarjeta al proceso serial. El sistema identifica al empleado activo y alterna entre `ENTRADA` y `SALIDA`. Las lecturas demasiado cercanas se rechazan como duplicadas.

El kiosco (`/attendance/kiosk`) muestra el resultado de la lectura y mantiene el foco preparado para la siguiente tarjeta.

### Marcaje manual

En `Marcaje manual rápido`:

1. Buscar por nombre, cédula o tarjeta.
2. Seleccionar uno o varios empleados.
3. Revisar el tipo sugerido y cambiarlo si corresponde.
4. Revisar la fecha y hora.
5. Registrar el lote y comprobar el resumen de resultados.

Atajos disponibles: `/` enfoca la búsqueda, `Enter` selecciona el primer resultado, `Backspace` elimina el último seleccionado y `Ctrl+Enter` registra el lote.

### Corrección controlada

En `Historial` se puede corregir un marcaje desde la acción `Corregir`. La operación permite cambiar empleado, tipo y hora, y exige un motivo de al menos cinco caracteres.

La corrección:

- Conserva el registro de marcaje; no existe borrado definitivo.
- Rechaza fechas futuras y empleados inexistentes.
- Registra usuario, fecha, motivo, valores anteriores y valores nuevos en `auditoria`.
- Requiere permisos de Administrador o RRHH.

## 4. Roles actuales

- `Administrador`: acceso total de administración y operación.
- `RRHH`: empleados, reportes, marcajes manuales y correcciones operativas.
- `Consulta`: lectura de información permitida, sin operaciones mutables.
- `Sistemas`: herramientas de sistema y backups, sin gestión general de empleados o usuarios.

El rol `Inspector` está definido como objetivo funcional en el checklist, pero debe considerarse pendiente hasta que exista una decisión explícita sobre sus permisos y su implementación completa.

## 5. Arranque y mantenimiento técnico

Arranque recomendado en Windows:

```bat
start_app.bat
```

Arranque manual:

```bat
.venv\Scripts\activate
python -m alembic upgrade head
python run.py
```

Pruebas:

```bat
.venv\Scripts\python.exe -m pytest -q
node --check .\app\static\js\main.js
git diff --check
```

Cuando `SERIAL_PORT` esté configurado, la aplicación debe ejecutarse con un solo worker para evitar lecturas duplicadas. Las migraciones nuevas deben añadirse en `alembic/versions/`; no se deben corregir instalaciones existentes modificando solo el script inicial de SQL.

## 6. Cómo documentar cada cambio futuro

Cada función nueva debe dejar cuatro rastros:

1. Checklist actualizado en `prioridades_inspector_garita.md` si pertenece al plan del inspector.
2. Explicación operativa aquí si cambia un flujo de usuario.
3. README actualizado si cambia instalación, despliegue, permisos o configuración.
4. Prueba automatizada para la regla de negocio o contrato que pueda romperse.

Al terminar cada bloque de trabajo se debe anotar:

- Qué cambió.
- Qué pantalla o endpoint afecta.
- Qué permisos requiere.
- Qué pruebas se ejecutaron.
- Qué queda pendiente o depende de una decisión.

## 7. Pendientes conocidos

Las prioridades 1, 2 y 3 del inspector están implementadas y validadas. Las prioridades 4 a 10 permanecen pendientes; no deben marcarse como terminadas solo porque exista una parte visual o un endpoint preliminar.

La siguiente etapa funcional prevista es el modo contingencia, pero se debe diseñar después de decidir dónde se almacenará la cola local y cómo se garantizará la sincronización con SQL Server.
