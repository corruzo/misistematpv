# Smoke test y despliegue del agente RFID

## 1. Migración y alta de una garita

Desde la raíz del repositorio, con el `.env` del servidor central configurado:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\create_gate_agent.py --id garita-prueba --name "Garita de prueba"
```

El segundo comando imprime `GARITA_ID` y `API_KEY`. Guarda la API key inmediatamente: la base de datos conserva únicamente su hash. Para rotarla:

```powershell
.\.venv\Scripts\python.exe scripts\create_gate_agent.py --id garita-prueba --name "Garita de prueba" --rotate
```

## 2. Smoke test sin lector físico

Usa el código de una tarjeta que exista en `empleados.codigo_tarjeta`:

```powershell
.\.venv\Scripts\python.exe scripts\test_agent_push.py `
  --url http://127.0.0.1:8000 `
  --garita-id garita-prueba `
  --api-key "API_KEY_GENERADA" `
  --card "CARD-001"
```

Resultado esperado:

- Heartbeat: HTTP `200`.
- Lectura nueva: HTTP `201`.
- Reenvío con el mismo `operation_id`: HTTP `200` y no duplica el marcaje.
- La lectura aparece en `/attendance/summary` mediante SSE/polling.
- El dashboard muestra el agente y lector en línea.

Una tarjeta inexistente o una lectura duplicada debe devolver un error funcional `4xx`; eso confirma que la API está respondiendo y que el agente la trataría como rechazo, no como error de red.

## 3. Instalación en la PC de garita

1. Instala Python 3.11+ y el controlador USB/COM del lector.
2. Copia `rfid_agent/`, `rfid_agent.env.example` e `install_rfid_agent.ps1` a una carpeta local, por ejemplo `C:\ProgramData\MarcajeTPV`.
3. Copia `rfid_agent.env.example` como `rfid_agent.env`.
4. Configura `PUERTO_COM`, `BAUD_RATE`, `URL_SERVIDOR`, `GARITA_ID`, `API_KEY` y `QUEUE_PATH`.
5. Comprueba el COM en el Administrador de dispositivos.
6. Desde PowerShell como administrador, ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\install_rfid_agent.ps1 -PythonPath "C:\ProgramData\MarcajeTPV\.venv\Scripts\python.exe" -ConfigPath "C:\ProgramData\MarcajeTPV\rfid_agent.env"
```

7. Verifica el servicio:

```powershell
Get-Service MarcajeTPVRfidAgent
```

8. Revisa que el heartbeat aparezca en el dashboard.
9. Desconecta temporalmente la red y presenta una tarjeta: debe aumentar la cola SQLite; al recuperar red debe vaciarse en orden.
10. No abras el navegador para que el agente capture tarjetas. El navegador solo sirve para visualizar eventos.

La API key debe protegerse con permisos de lectura solo para la cuenta del servicio. Usa HTTPS en producción.
