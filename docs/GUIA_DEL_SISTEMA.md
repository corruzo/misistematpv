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
| Gestionar empleados | Gestión de personal | `/employees` | Desarrollador o RRHH; Inspector solo consulta directorio operativo |
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

El lector RFID es atendido por el servicio independiente `rfid_agent` instalado en la PC de la garita. Cada lectura recibe allí su `timestamp_lectura` UTC con offset y se persiste primero en SQLite. Los errores de red, timeout y respuestas `5xx` conservan la cabeza de la cola FIFO con backoff exponencial y jitter; las respuestas `4xx` pasan a `rejected_scans` y no bloquean las siguientes lecturas. La cola no descarta automáticamente registros al llenarse.

El agente envía las lecturas a `POST /api/v1/asistencia/lectura` usando una API key Bearer específica de la garita. El servidor conserva la hora histórica recibida y aplica las reglas centrales de asistencia. `timestamp_envio` permite advertir desfases del reloj sin confundir una lectura acumulada offline con una lectura reciente.

El heartbeat se envía frecuentemente para detectar disponibilidad, pero el servidor solo persiste `last_seen` si cambió el estado o transcurrió `AGENT_HEARTBEAT_PERSIST_SECONDS` (60 segundos por defecto). La UI consulta ese estado remoto y muestra si el agente está en línea, tiene lecturas en cola o tiene el lector desconectado.

El kiosco (`/attendance/kiosk`) muestra el resultado de la lectura y mantiene el foco preparado para la siguiente tarjeta.

Las pantallas operativas reciben marcajes y alertas mediante SSE (`/api/live`). El canal espera sin consultar la base de datos mientras no hay cambios y se reconcilia periódicamente para cubrir reinicios, desconexiones o procesos separados. El kiosco usa el mismo canal y conserva una reconciliación de baja frecuencia como respaldo.

El panel de resumen muestra alertas por secuencias repetidas, marcajes demasiado cercanos, salidas sin entrada, empleados retirados o suspendidos, posibles permanencias desde el día anterior y permanencias superiores a `PROLONGED_STAY_HOURS` (12 horas por defecto). La exportación operativa está disponible como CSV desde `Historial`; respeta los filtros aplicados y requiere permiso de lectura.

### Marcaje manual

En `Marcaje manual rápido`:

1. Buscar por nombre, cédula o tarjeta.
2. Seleccionar uno o varios empleados.
3. Revisar el tipo sugerido y cambiarlo si corresponde.
4. Revisar la fecha y hora.
5. Registrar el lote y comprobar el resumen de resultados.

Si se pierde la conexión o el servidor devuelve un error temporal, el lote se guarda localmente en el navegador del usuario y se sincroniza al recuperar la conexión. Los errores funcionales, como un empleado suspendido, no se reintentan automáticamente y quedan señalados para revisión. Cada marcaje pendiente tiene una identidad única para evitar duplicados durante los reintentos.

Atajos disponibles: `/` enfoca la búsqueda, `Enter` selecciona el primer resultado, `Backspace` elimina el último seleccionado y `Ctrl+Enter` registra el lote.

### Corrección controlada

En `Historial` se puede corregir un marcaje desde la acción `Corregir`. La operación permite cambiar empleado, tipo y hora, y exige un motivo de al menos cinco caracteres.

La corrección:

- Conserva el registro de marcaje; no existe borrado definitivo.
- Rechaza fechas futuras y empleados inexistentes.
- Registra usuario, fecha, motivo, valores anteriores y valores nuevos en `auditoria`.
- Requiere permisos de Administrador o RRHH.

## 4. Matriz de permisos actual

La aplicación usa únicamente estos roles canónicos:

| Rol | Datos maestros | Operación de asistencia | Sistema |
| --- | --- | --- | --- |
| `Desarrollador` | Lectura y administración de empleados, organización y usuarios | Lectura, registro y corrección | Backups y configuración |
| `RRHH` | Lectura y administración de empleados | Lectura, registro y corrección | Sin administración |
| `Inspector` | Directorio operativo: nombre, gerencia, departamento y estatus | Resumen completo, marcaje manual e historial | Sin fichas, edición, eliminación ni administración |

La matriz se define en `app/core/auth.py`. Los módulos deben solicitar permisos por capacidad, no duplicar comparaciones de nombres de rol. Los nombres `Administrador`, `Consulta` y `Sistemas` no son roles implementados actualmente y no deben usarse en nuevas funciones.

## 5. Arranque y mantenimiento técnico

Arranque recomendado en Windows:

```bat
start_app.bat
```

El servidor escucha en `0.0.0.0:8000`. Al iniciar, el lanzador muestra la IP local del equipo; usa `http://<IP-LOCAL-DEL-EQUIPO>:8000/` desde otra PC de la red.

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

El servidor central no requiere `SERIAL_PORT`; el puerto COM se configura únicamente en `rfid_agent.env`. Las migraciones nuevas deben añadirse en `alembic/versions/`; no se deben corregir instalaciones existentes modificando solo el script inicial de SQL.

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

### Propuesta futura: resumen de horas para nómina

La ficha de empleados se mantiene enfocada en datos maestros. El cálculo de horas debe vivir en un módulo separado de asistencia y nómina, usando los marcajes como fuente operativa, pero sin convertirlos automáticamente en conceptos salariales hasta definir la política laboral.

Alcance propuesto:

- Horas acumuladas del día actual, de la semana y del mes anterior.
- Resumen por empleado, departamento, gerencia y período.
- Separación entre jornada ordinaria, horas extra, ausencias, días no laborados y turnos incompletos.
- Identificación de entradas sin salida y correcciones pendientes antes de cerrar un período.
- Reglas configurables para feriados, descansos, tolerancias, turnos nocturnos y sobretiempo.
- Exportación de un resumen validado para el módulo de nómina.

Decisiones pendientes antes de implementarlo: calendario laboral oficial, definición de semana, tratamiento de medianoche y turnos nocturnos, redondeos, pausas, feriados, permisos, vacaciones, horas extra autorizadas y quién aprueba el cierre mensual. Esta función no debe calcular pagos por sí sola ni modificar los marcajes originales.

Las prioridades 1, 2 y 3 del inspector están implementadas y validadas. La prioridad 4 está implementada parcialmente para la cola de marcajes manuales en el navegador; la cola offline del lector RFID y una cola local cifrada fuera del navegador permanecen pendientes. Las prioridades 5 a 10 permanecen pendientes; no deben marcarse como terminadas solo porque exista una parte visual o un endpoint preliminar.

La siguiente etapa funcional prevista es completar el modo contingencia del lector RFID y decidir si se requiere una cola local cifrada fuera del navegador.
