# Manual de instalación y acceso en red local para MarcajeTPV

Este documento explica exactamente qué hacer cuando el sistema se va a instalar en la computadora que va a alojarlo en la empresa, para que otras PCs de la misma red puedan abrirlo desde un navegador.

## 1. Objetivo

Dejar la aplicación funcionando en una máquina servidor dentro de la red local y permitir el acceso desde otras estaciones con una URL como:

- http://10.0.0.166:8000
- o http://marcaje-tpv:8000

## 2. Requisitos previos

La máquina donde se va a alojar la app debe tener:

- Windows 10 o 11
- Python 3.11 o superior
- Acceso local al proyecto
- SQL Server instalado o accesible
- Conexión en la misma red local
- Puerto 8000 disponible

## 3. Preparar la aplicación en la máquina servidor

### 3.1 Entrar en la carpeta del proyecto

Abre PowerShell o CMD y entra a la carpeta del proyecto:

```powershell
cd C:\Users\Ngarcia\Desktop\misistematpv
```

### 3.2 Activar el entorno virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea scripts, ejecuta antes:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Luego activa el entorno:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3.3 Verificar que el archivo .env está bien

Revisa el archivo `.env` y confirma que tenga algo parecido a esto:

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
COOKIE_SECURE=false
TRUST_SERVER_CERTIFICATE=true
CSRF_ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000,http://10.0.0.166:8000,http://marcaje-tpv:8000
```

IMPORTANTE:
- `APP_HOST=0.0.0.0` hace que el servidor escuche en todas las interfaces de red.
- `APP_PORT=8000` es el puerto web del sistema.
- `CSRF_ALLOWED_ORIGINS` debe incluir la IP o alias que usarán los navegadores desde la red local.

## 4. Arrancar la aplicación

La forma recomendada del proyecto es:

```powershell
.\start_app.bat
```

Si quieres arrancarlo manualmente:

```powershell
python run.py
```

Cuando arranque, deberías ver algo como:

```text
Iniciando MarcajeTPV en 0.0.0.0:8000...
Uvicorn running on http://0.0.0.0:8000
Sistema listo: http://10.0.0.166:8000/
```

## 5. Comprobar si la app responde localmente

En la misma máquina servidor abre el navegador y prueba:

```text
http://127.0.0.1:8000
```

Si funciona, el sistema está levantado correctamente.

## 6. Abrir el puerto 8000 en el Firewall de Windows

### Opción A: con la interfaz gráfica

1. Pulsa Windows + R
2. Escribe:
   ```powershell
   wf.msc
   ```
3. Entra en "Reglas de entrada"
4. Botón derecho → "Nueva regla"
5. Selecciona:
   - Puerto
   - Siguiente
6. Selecciona:
   - TCP
   - Puertos específicos: 8000
   - Siguiente
7. Selecciona:
   - Permitir la conexión
   - Siguiente
8. Marca:
   - Dominio
   - Privado
   - Público
   - Siguiente
9. Pon el nombre:
   - MarcajeTPV-8000
10. Finalizar

### Opción B: con PowerShell (rápido)

Ejecuta esta instrucción como administrador:

```powershell
New-NetFirewallRule -DisplayName "MarcajeTPV-8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000
```

Esto crea la regla directamente.

## 7. Comprobar que el puerto está abierto

Desde la máquina servidor:

```powershell
netstat -ano | findstr :8000
```

Debe mostrar una entrada con estado LISTENING.

## 8. Resolver la IP de la máquina servidor

En la máquina alojada, ejecuta:

```powershell
ipconfig
```

Busca la línea:

```text
Dirección IPv4 . . . . . . . . . : 10.0.0.166
```

En este caso, la URL de acceso desde otra PC dentro de la red sería:

```text
http://10.0.0.166:8000
```

## 9. Usar un nombre local en la red (opcional pero recomendable)

Si quieres usar algo más fácil como:

```text
http://marcaje-tpv:8000
```

### Opción A: Hosts local de Windows

En la máquina SERVIDOR:

1. Abre PowerShell como administrador
2. Ejecuta:
   ```powershell
   notepad C:\Windows\System32\drivers\etc\hosts
   ```
3. Añade al final esta línea:
   ```text
   10.0.0.166    marcaje-tpv
   ```
4. Guarda

Luego, desde cualquier equipo de la red, si también añaden ese mismo registro al hosts, puede usar:

```text
http://marcaje-tpv:8000
```

### Opción B: DNS interno de la red

La mejor solución para una empresa es poner un registro DNS interno, por ejemplo:

```text
marcaje-tpv  ->  10.0.0.166
```

Esto deja el acceso limpio para todas las PCs sin tocar cada host manualmente.

## 10. Probar desde otra PC de la red

Desde otra máquina conectada a la misma LAN, abre cualquiera de estas URLs:

```text
http://10.0.0.166:8000
```

o

```text
http://marcaje-tpv:8000
```

Si se abre la pantalla del sistema, la configuración de red está funcionando.

## 11. Si aparece un error de acceso o CSRF

El proyecto incluye validación de origen CSRF. Si la URL de otra máquina no está en `CSRF_ALLOWED_ORIGINS`, el navegador puede bloquear la sesión.

Asegúrate de que en `.env` aparecen los orígenes admitidos, por ejemplo:

```env
CSRF_ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000,http://10.0.0.166:8000,http://marcaje-tpv:8000
```

Si usas otro nombre o IP, añádelo exactamente.

## 12. Recomendación para producción real en la empresa

Para una instalación de empresa, lo ideal es:

1. Instalar la app en una máquina fija.
2. Dejar el sistema siempre encendido.
3. Abrir puerto 8000 en el firewall.
4. Resolver el nombre interno con DNS.
5. Mantener la IP estática de la máquina servidor.
6. Dar acceso por nombre, no por IP.

## 13. Checklist final antes de dejarlo operativo

- [ ] La máquina servidor está encendida
- [ ] La app está arrancada con `start_app.bat`
- [ ] El puerto 8000 está abierto en Windows Firewall
- [ ] El sistema responde en `http://127.0.0.1:8000`
- [ ] La IP local del servidor está identificada
- [ ] Opción de acceso por IP funciona desde otra PC
- [ ] Si se usa alias, está definido en hosts o DNS
- [ ] El navegador abre correctamente la app desde la red
- [ ] La base de datos SQL Server está accesible desde esa máquina
- [ ] El lector HID está conectado si se desea lectura en tiempo real

## 14. Resumen final

La instalación real en empresa queda así:

- la app corre en una máquina servidor,
- escucha en `0.0.0.0:8000`,
- el firewall deja pasar el puerto 8000,
- se accede desde la red por IP o por un nombre local,
- el nombre recomendado es `marcaje-tpv`.

## 15. Ejemplo final de acceso

Desde otra máquina de la red.local:

```text
http://marcaje-tpv:8000
```

Si el nombre no existe todavía, usa:

```text
http://10.0.0.166:8000
```

---

Si quieres, en el siguiente paso puedo dejarte también un segundo documento más corto, tipo "checklist de despliegue final" para imprimir o guardar en la carpeta del proyecto, con solo la parte operativa y sin explicación larga.
