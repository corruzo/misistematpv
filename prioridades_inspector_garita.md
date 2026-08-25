# Prioridades de implementación: Inspector de garita

Checklist para desarrollar las funciones operativas del rol Inspector de asistencia.

## Cómo mantener este documento

Este archivo es el mapa de avance funcional, no un manual de uso. Marca una casilla únicamente cuando la función esté implementada, probada y disponible en la pantalla o endpoint correspondiente. Para cada bloque terminado, documenta el flujo operativo en [docs/GUIA_DEL_SISTEMA.md](docs/GUIA_DEL_SISTEMA.md) y deja sin marcar cualquier parte que dependa de una decisión pendiente.

## Prioridad 1: Panel de control de garita

- [x] Mostrar personas actualmente dentro.
- [x] Mostrar últimas entradas y salidas.
- [x] Mostrar empleados esperados que aún no han ingresado.
- [x] Mostrar el último marcaje realizado.
- [x] Mostrar el estado del lector RFID.
- [x] Mostrar fecha y hora actualizadas.
- [x] Mostrar alertas de errores o marcajes duplicados.

## Prioridad 2: Marcaje manual rápido

- [x] Buscar por nombre, cédula o tarjeta.
- [x] Seleccionar varios empleados.
- [x] Proponer automáticamente Entrada o Salida.
- [x] Permitir corregir Entrada o Salida antes de registrar.
- [x] Confirmar cuántos registros fueron procesados.
- [x] Añadir atajos de teclado para la operación diaria.

## Prioridad 3: Corrección controlada de marcajes

- [x] Permitir corregir el tipo de marcaje.
- [x] Permitir corregir la hora.
- [x] Permitir corregir el empleado asociado.
- [x] Exigir un motivo obligatorio.
- [x] Registrar usuario, fecha y hora de la corrección.
- [x] Mostrar valor anterior y valor nuevo.
- [x] Impedir el borrado definitivo de marcajes.

## Prioridad 4: Modo contingencia

- [ ] Activar modo contingencia cuando falle el lector, la red o SQL Server.
- [ ] Guardar marcajes pendientes en una cola local segura.
- [ ] Mostrar el estado pendiente de sincronización.
- [ ] Sincronizar automáticamente al recuperar la conexión.
- [ ] Evitar registros duplicados durante la sincronización.
- [ ] Mostrar errores de sincronización para revisión.

## Prioridad 5: Alertas de inconsistencias

- [ ] Detectar dos entradas consecutivas.
- [ ] Detectar dos salidas consecutivas.
- [ ] Detectar marcajes demasiado cercanos.
- [ ] Detectar empleados retirados o suspendidos.
- [ ] Detectar marcajes fuera del horario permitido.
- [ ] Detectar salidas sin entrada previa.
- [ ] Detectar personas dentro desde el día anterior.

## Prioridad 6: Entrega de turno

- [ ] Identificar inspector saliente.
- [ ] Identificar inspector entrante.
- [ ] Registrar hora del cambio.
- [ ] Registrar observaciones.
- [ ] Mostrar incidencias pendientes.
- [ ] Registrar cantidad de personas dentro al entregar el turno.

## Prioridad 7: Protocolo de emergencia

- [ ] Mostrar personas actualmente dentro.
- [ ] Mostrar último marcaje de cada persona.
- [ ] Mostrar departamento y cargo.
- [ ] Generar listado imprimible.
- [ ] Permitir exportar el listado.
- [ ] Mostrar fecha y hora de generación.
- [ ] Mantener esta función en modo solo lectura.

## Prioridad 8: Gestión de incidencias

- [ ] Registrar tarjeta olvidada.
- [ ] Registrar tarjeta dañada.
- [ ] Registrar empleado sin identificación.
- [ ] Registrar lector fuera de servicio.
- [ ] Registrar correcciones manuales.
- [ ] Registrar persona no reconocida.
- [ ] Usar estados Abierta, En revisión y Resuelta.

## Prioridad 9: Alertas de permanencia prolongada

- [ ] Detectar permanencia superior al umbral configurado.
- [ ] Detectar entradas sin salida al finalizar la jornada.
- [ ] Mostrar duración dentro de la empresa.
- [ ] Permitir configurar umbrales desde Sistemas.
- [ ] Evitar alertas repetidas para la misma persona.

## Prioridad 10: Exportación operativa

- [ ] Exportar marcajes del turno.
- [ ] Exportar personas presentes.
- [ ] Exportar incidencias del día.
- [ ] Exportar resumen por empleado.
- [ ] Comenzar con formato CSV.
- [ ] Restringir la exportación a información operativa necesaria.

## Permisos del rol Inspector

### Puede hacer

- [ ] Consultar empleados.
- [ ] Consultar presencia actual.
- [ ] Registrar marcajes manuales.
- [ ] Corregir marcajes con motivo.
- [ ] Consultar el historial necesario para su operación.
- [ ] Registrar incidencias.
- [ ] Exportar información operativa.

### No puede hacer

- [ ] Crear usuarios.
- [ ] Cambiar roles.
- [ ] Crear empleados.
- [ ] Modificar la organización.
- [ ] Ejecutar backups.
- [ ] Cambiar la configuración del lector.
- [ ] Eliminar registros.
- [ ] Cambiar políticas del sistema.
