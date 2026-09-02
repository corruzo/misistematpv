# Manual de preparación de Windows para pantalla de kiosco / Inspector

Este documento describe cómo dejar preparado un equipo Windows para que muestre únicamente la pantalla del sistema de asistencia y no permita salir ni mover la vista, salvo para un usuario de desarrollo o administrador.

## Objetivo

Configurar el equipo del monitor para que:

- inicie directamente la pantalla del kiosco,
- no permita salir del navegador ni de la aplicación,
- bloquee la posibilidad de cerrar, minimizar o mover la ventana,
- permita que un usuario desarrollador pueda salir o acceder a la configuración cuando sea necesario.

## Recomendación de arquitectura

La seguridad real no la da solamente la página web. La capa fuerte debe estar en Windows.

Se recomienda:

- usar un equipo dedicado para el monitor,
- crear un usuario específico para el kiosk,
- usar Microsoft Edge en modo kiosko,
- arrancar la URL de la pantalla del inspector,
- dejar la sesión en un usuario sin acceso a funciones del sistema,
- permitir acceso administrativo solo a usuarios desarrolladores desde un inicio de sesión distinto.

---

## Requisitos mínimos

- Windows 10 Pro / Enterprise / Education
- Microsoft Edge instalado
- Conexión al sistema de asistencia
- URL de la pantalla del kiosco conocida, por ejemplo:
  - http://localhost:8000/attendance/kiosk
  - o la IP del servidor si se usa en red local

Si el equipo usa Windows 10 Home, la opción de Acceso para kioscos no viene disponible de forma nativa. En ese caso se debe usar un usuario dedicado y arrancar el navegador con modo kiosko desde autoinicio.

---

## Opción recomendada: Acceso para kioscos (Assigned Access)

### 1. Crear un usuario dedicado

1. Abrir Configuración.
2. Ir a Cuentas > Familia y otros usuarios.
3. Agregar un usuario para el kiosco, por ejemplo: `kiosk`.
4. Dejar ese usuario sin permisos de administración.
5. No instalar software adicional en esa cuenta.

### 2. Activar Acceso para kioscos

1. Ir a Configuración.
2. Entrar en Cuentas > Acceso para kioscos.
3. Seleccionar Configurar un acceso para kioscos.
4. Elegir el usuario creado, por ejemplo `kiosk`.
5. Elegir Microsoft Edge como la aplicación de kiosco.
6. Configurar la URL del sistema, por ejemplo:
   - http://localhost:8000/attendance/kiosk
7. Guardar la configuración.

### 3. Probar el arranque

1. Cerrar la sesión actual.
2. Iniciar sesión con el usuario del kiosco.
3. Verificar que se abre únicamente la pantalla del sistema.
4. Comprobar que no se puede salir a la aplicación de escritorio.

### 4. Salir del kiosco cuando sea necesario

Para un usuario desarrollador o administrador, debe existir otro usuario con permisos completos y una forma de iniciar sesión normal para salir del acceso para kioscos.

---

## Opción alternativa: arranque directo del navegador en modo kiosko

Esto sirve cuando no se dispone de Assigned Access o cuando se quiere arrancar el navegador directamente al iniciar Windows.

### 1. Crear acceso directo a Edge

1. Abrir el Explorador de archivos.
2. Ir a la carpeta del ejecutable de Edge, normalmente:
   - C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
3. Crear un acceso directo en el Escritorio.
4. Hacer clic derecho sobre el acceso directo.
5. Seleccionar Propiedades.

### 2. Agregar el parámetro kiosko

En el campo Objetivo, dejar algo como:

```powershell
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk "http://localhost:8000/attendance/kiosk"
```

Si usas Chrome:

```powershell
"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk "http://localhost:8000/attendance/kiosk"
```

### 3. Ponerlo en Inicio

1. Presionar Win + R.
2. Escribir:
   ```powershell
   shell:startup
   ```
3. Arrastrar el acceso directo a esa carpeta.

Con esto, cada vez que el usuario inicie sesión, el navegador abrirá la pantalla del kiosco automáticamente.

---

## Recomendación para que la aplicación web también esté bloqueada

Además de Windows, la pantalla del kiosco en la app debe tener defensas del navegador para impedir:

- minimizar la ventana,
- cerrarla,
- abrir menús del navegador,
- salir con teclado o atajos,
- cambiar el foco a otra pestaña o ventana,
- abrir contexto con clic derecho.

Esto debe aplicarse solo cuando el rol sea `Inspector`, y no cuando sea `Desarrollador`.

En la aplicación, el bloqueo debe estar en la lógica de la vista del kiosco y no en todo el sistema.

---

## Configuración recomendada del equipo

### Usuario del monitor

- usuario: `kiosk`
- sin permisos de administrador
- sin acceso a escritorio normal
- solo el navegador del sistema

### Usuario de desarrollo

- usuario normal con permisos elevados
- puede entrar para diagnosticar o salir del kiosco si se requiere
- no usarlo para la operación diaria del monitor

### Equipo físico

- evitar acceso directo a teclado y mouse del operador normal,
- dejar la pantalla en la posición adecuada,
- no permitir acceso al escritorio ni a tareas del sistema,
- usar un monitor fijo y una sesión dedicada.

---

## Verificación final

Después de configurar el equipo, comprobar lo siguiente:

1. Al iniciar sesión con el usuario de kiosco, se abre la pantalla del sistema.
2. La ventana no puede minimizarse ni cerrarse desde el navegador.
3. El usuario no tiene acceso al escritorio fuera de la app.
4. La pantalla permanece visible y operativa.
5. Un usuario desarrollador puede entrar con otra sesión para realizar tareas administrativas.

---

## Recomendación final

Para un monitor de inspección, lo más seguro es combinar ambas capas:

- Windows en modo kiosco o Assigned Access,
- y protección adicional dentro de la app para Inspector.

Esto da un nivel real de seguridad y evita que la pantalla pueda ser manipulada por personal no autorizado.

---

## Resumen rápido

Si quieres la solución más limpia y robusta:

1. Crear usuario `kiosk`.
2. Activar Acceso para kioscos.
3. Elegir Edge.
4. Abrir la URL del sistema.
5. Dejar la app con bloqueo adicional para Inspector.
6. Mantener un usuario de desarrollo para salir y hacer mantenimiento.

---

## Nota final

Este documento debe dejarse en la carpeta raíz del proyecto como referencia de despliegue del equipo de monitoreo y del módulo del kiosco.
