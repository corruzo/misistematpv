param(
    [string]$ServiceName = 'MarcajeTPVRfidAgent',
    [string]$PythonPath = "$PSScriptRoot\.venv\Scripts\python.exe",
    [string]$ConfigPath = "$PSScriptRoot\rfid_agent.env"
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $PythonPath)) {
    $systemPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $systemPython) {
        throw "No se encontró Python. Instala Python 3.11+ y vuelve a ejecutar este script."
    }
    Write-Output 'Creando entorno virtual del agente...'
    & $systemPython.Source -m venv "$PSScriptRoot\.venv"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno virtual del agente.' }
}

& $PythonPath -m pip install --disable-pip-version-check -r "$PSScriptRoot\rfid_agent\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias del agente.' }
if (-not (Test-Path $ConfigPath)) {
    throw "Copia rfid_agent.env.example a rfid_agent.env y configúralo antes de instalar el servicio."
}

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
}

$binPath = "`"$PythonPath`" `"$PSScriptRoot\rfid_agent\run_service.py`" --config `"$ConfigPath`""
New-Service -Name $ServiceName -BinaryPathName $binPath -DisplayName 'MarcajeTPV RFID Agent' -Description 'Captura RFID y sincroniza marcajes con el servidor central.' -StartupType Automatic
& sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Null
Start-Service -Name $ServiceName
Write-Output "Servicio $ServiceName instalado e iniciado."