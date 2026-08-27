SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF DB_ID('misistema_db') IS NULL
BEGIN
    CREATE DATABASE misistema_db;
END
GO

USE misistema_db;
GO

-- 2) Crear tablas de organización
IF OBJECT_ID('dbo.gerencias', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.gerencias (
        id INT IDENTITY(1,1) PRIMARY KEY,
        nombre NVARCHAR(150) NOT NULL UNIQUE,
        descripcion NVARCHAR(500) NULL,
        estado NVARCHAR(20) NOT NULL DEFAULT 'Activo',
        fecha_creacion DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_gerencias_estado CHECK (estado IN ('Activo', 'Inactivo'))
    );
END
GO

IF OBJECT_ID('dbo.departamentos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.departamentos (
        id INT IDENTITY(1,1) PRIMARY KEY,
        nombre NVARCHAR(150) NOT NULL,
        descripcion NVARCHAR(500) NULL,
        estado NVARCHAR(20) NOT NULL DEFAULT 'Activo',
        fecha_creacion DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        gerencia_id INT NOT NULL,
        CONSTRAINT FK_departamentos_gerencias FOREIGN KEY (gerencia_id) REFERENCES dbo.gerencias(id) ON DELETE NO ACTION,
        CONSTRAINT CK_departamentos_estado CHECK (estado IN ('Activo', 'Inactivo')),
        CONSTRAINT UX_departamentos_gerencia_nombre UNIQUE (gerencia_id, nombre)
    );
END
GO

IF OBJECT_ID('dbo.cargos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.cargos (
        id INT IDENTITY(1,1) PRIMARY KEY,
        nombre NVARCHAR(150) NOT NULL,
        descripcion NVARCHAR(500) NULL,
        estado NVARCHAR(20) NOT NULL DEFAULT 'Activo',
        fecha_creacion DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        departamento_id INT NOT NULL,
        CONSTRAINT FK_cargos_departamentos FOREIGN KEY (departamento_id) REFERENCES dbo.departamentos(id) ON DELETE NO ACTION,
        CONSTRAINT CK_cargos_estado CHECK (estado IN ('Activo', 'Inactivo')),
        CONSTRAINT UX_cargos_departamento_nombre UNIQUE (departamento_id, nombre)
    );
END
GO

IF OBJECT_ID('dbo.departamentos', 'U') IS NOT NULL
BEGIN
        DECLARE @departamento_unique_constraint NVARCHAR(256);
        SELECT TOP 1 @departamento_unique_constraint = QUOTENAME(i.name)
        FROM sys.indexes i
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE i.object_id = OBJECT_ID('dbo.departamentos') AND i.is_unique = 1 AND i.is_unique_constraint = 1
            AND c.name = 'nombre';
        IF @departamento_unique_constraint IS NOT NULL
                EXEC('ALTER TABLE dbo.departamentos DROP CONSTRAINT ' + @departamento_unique_constraint);
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_departamentos_gerencia_nombre' AND object_id = OBJECT_ID('dbo.departamentos'))
                CREATE UNIQUE INDEX UX_departamentos_gerencia_nombre ON dbo.departamentos(gerencia_id, nombre);
END
GO

IF OBJECT_ID('dbo.cargos', 'U') IS NOT NULL
BEGIN
        DECLARE @cargo_unique_constraint NVARCHAR(256);
        SELECT TOP 1 @cargo_unique_constraint = QUOTENAME(i.name)
        FROM sys.indexes i
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE i.object_id = OBJECT_ID('dbo.cargos') AND i.is_unique = 1 AND i.is_unique_constraint = 1
            AND c.name = 'nombre';
        IF @cargo_unique_constraint IS NOT NULL
                EXEC('ALTER TABLE dbo.cargos DROP CONSTRAINT ' + @cargo_unique_constraint);
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_cargos_departamento_nombre' AND object_id = OBJECT_ID('dbo.cargos'))
                CREATE UNIQUE INDEX UX_cargos_departamento_nombre ON dbo.cargos(departamento_id, nombre);
END
GO

-- 3) Crear tabla empleados con clave foránea hacia organización
IF OBJECT_ID('dbo.empleados', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.empleados (
        id INT IDENTITY(1,1) PRIMARY KEY,
        cedula NVARCHAR(50) NOT NULL UNIQUE,
        nombre_apellido NVARCHAR(200) NOT NULL,
        telefono NVARCHAR(30) NULL,
        email NVARCHAR(254) NULL,
        contacto_emergencia_parentesco NVARCHAR(100) NULL,
        contacto_emergencia_telefono NVARCHAR(30) NULL,
        departamento_id INT NOT NULL,
        cargo_id INT NOT NULL,
        estado NVARCHAR(50) NOT NULL DEFAULT 'Activo',
        tipo_nomina NVARCHAR(50) NULL,
        foto_url NVARCHAR(300) NULL,
        fecha_creacion DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_empleados_departamentos FOREIGN KEY (departamento_id) REFERENCES dbo.departamentos(id) ON DELETE NO ACTION,
        CONSTRAINT FK_empleados_cargos FOREIGN KEY (cargo_id) REFERENCES dbo.cargos(id) ON DELETE NO ACTION,
        CONSTRAINT CK_empleados_estado CHECK (estado IN ('Activo', 'Vacaciones', 'Retirado', 'Suspendido'))
    );
END
GO

IF COL_LENGTH('dbo.empleados', 'telefono') IS NULL
    ALTER TABLE dbo.empleados ADD telefono NVARCHAR(30) NULL;
IF COL_LENGTH('dbo.empleados', 'email') IS NULL
    ALTER TABLE dbo.empleados ADD email NVARCHAR(254) NULL;
IF COL_LENGTH('dbo.empleados', 'contacto_emergencia_parentesco') IS NULL
    ALTER TABLE dbo.empleados ADD contacto_emergencia_parentesco NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.empleados', 'contacto_emergencia_telefono') IS NULL
    ALTER TABLE dbo.empleados ADD contacto_emergencia_telefono NVARCHAR(30) NULL;
GO

IF COL_LENGTH('dbo.empleados', 'fecha_nacimiento') IS NULL
BEGIN
    ALTER TABLE dbo.empleados ADD fecha_nacimiento DATE NULL;
END
GO

IF COL_LENGTH('dbo.empleados', 'codigo_tarjeta') IS NULL
BEGIN
    ALTER TABLE dbo.empleados ADD codigo_tarjeta NVARCHAR(100) NULL;
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_empleados_codigo_tarjeta' AND object_id = OBJECT_ID('dbo.empleados'))
BEGIN
    CREATE UNIQUE INDEX UX_empleados_codigo_tarjeta ON dbo.empleados(codigo_tarjeta) WHERE codigo_tarjeta IS NOT NULL;
END
GO

IF OBJECT_ID('dbo.marcajes_asistencia', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.marcajes_asistencia (
        id INT IDENTITY(1,1) PRIMARY KEY,
        empleado_id INT NOT NULL,
        tipo NVARCHAR(10) NOT NULL,
        fecha_hora DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        origen NVARCHAR(20) NOT NULL,
        CONSTRAINT FK_marcajes_asistencia_empleados FOREIGN KEY (empleado_id) REFERENCES dbo.empleados(id),
        CONSTRAINT CK_marcajes_asistencia_tipo CHECK (tipo IN ('ENTRADA', 'SALIDA')),
        CONSTRAINT CK_marcajes_asistencia_origen CHECK (origen IN ('PUERTO_COM', 'MANUAL_ADMIN'))
    );
    CREATE INDEX IX_marcajes_asistencia_empleado_fecha ON dbo.marcajes_asistencia(empleado_id, fecha_hora DESC);
END
GO

-- 4) Usuarios del sistema
IF OBJECT_ID('dbo.usuarios', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.usuarios (
        id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(50) NOT NULL UNIQUE,
        nombre NVARCHAR(150) NOT NULL,
        password_hash NVARCHAR(500) NOT NULL,
        rol NVARCHAR(30) NOT NULL DEFAULT 'Desarrollador',
        activo BIT NOT NULL DEFAULT 1,
        fecha_creacion DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        ultimo_acceso DATETIME2 NULL,
        CONSTRAINT CK_usuarios_rol CHECK (rol IN ('Desarrollador', 'RRHH', 'Inspector'))
    );
END
GO

IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_usuarios_rol' AND parent_object_id = OBJECT_ID('dbo.usuarios'))
BEGIN
    ALTER TABLE dbo.usuarios DROP CONSTRAINT CK_usuarios_rol;
END
GO

UPDATE dbo.usuarios SET rol = CASE
    WHEN rol IN ('Administrador', 'Sistemas') THEN 'Desarrollador'
    WHEN rol = 'Consulta' THEN 'Inspector'
    WHEN rol = 'RRHH' THEN 'RRHH'
    ELSE 'Inspector'
END
WHERE rol IS NULL OR rol NOT IN ('Desarrollador', 'RRHH', 'Inspector');
GO

ALTER TABLE dbo.usuarios ADD CONSTRAINT CK_usuarios_rol CHECK (rol IN ('Desarrollador', 'RRHH', 'Inspector'));
GO

-- 5) Sesiones de inicio de sesión; solo se guarda el hash del token
IF OBJECT_ID('dbo.sesiones_usuario', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.sesiones_usuario (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        token_hash CHAR(64) NOT NULL UNIQUE,
        expires_at DATETIME2 NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_sesiones_usuario_usuario FOREIGN KEY (user_id) REFERENCES dbo.usuarios(id) ON DELETE CASCADE
    );
    CREATE INDEX IX_sesiones_usuario_user_id ON dbo.sesiones_usuario(user_id);
    CREATE INDEX IX_sesiones_usuario_expires_at ON dbo.sesiones_usuario(expires_at);
END
GO

IF OBJECT_ID('dbo.auditoria', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.auditoria (
        id INT IDENTITY(1,1) PRIMARY KEY,
        usuario_id INT NULL,
        accion NVARCHAR(50) NOT NULL,
        entidad NVARCHAR(50) NOT NULL,
        entidad_id INT NULL,
        datos_antes NVARCHAR(MAX) NULL,
        datos_despues NVARCHAR(MAX) NULL,
        fecha DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_auditoria_usuario FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id) ON DELETE NO ACTION
    );
    CREATE INDEX IX_auditoria_usuario_fecha ON dbo.auditoria(usuario_id, fecha DESC);
    CREATE INDEX IX_auditoria_entidad_fecha ON dbo.auditoria(entidad, entidad_id, fecha DESC);
END
GO

IF OBJECT_ID('dbo.eventos_acceso_denegado', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.eventos_acceso_denegado (
        id INT IDENTITY(1,1) PRIMARY KEY,
        empleado_id INT NULL,
        empleado_nombre NVARCHAR(200) NOT NULL,
        estado NVARCHAR(20) NOT NULL,
        fecha_hora DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_eventos_acceso_denegado_empleado FOREIGN KEY (empleado_id) REFERENCES dbo.empleados(id) ON DELETE NO ACTION,
        CONSTRAINT CK_eventos_acceso_denegado_estado CHECK (estado IN ('Retirado', 'Suspendido'))
    );
    CREATE INDEX IX_eventos_acceso_denegado_fecha_id ON dbo.eventos_acceso_denegado(fecha_hora, id);
END
GO

IF OBJECT_ID('dbo.notificaciones', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.notificaciones (
        id INT IDENTITY(1,1) PRIMARY KEY,
        usuario_id INT NOT NULL,
        tipo NVARCHAR(40) NOT NULL,
        prioridad NVARCHAR(15) NOT NULL,
        titulo NVARCHAR(150) NOT NULL,
        mensaje NVARCHAR(MAX) NOT NULL,
        creada_en DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        leida_en DATETIME2 NULL,
        descartada_en DATETIME2 NULL,
        CONSTRAINT FK_notificaciones_usuario FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id) ON DELETE CASCADE,
        CONSTRAINT CK_notificaciones_prioridad CHECK (prioridad IN ('critica', 'advertencia', 'informativa')),
        CONSTRAINT CK_notificaciones_tipo CHECK (tipo IN ('acceso_no_autorizado', 'pase_temporal', 'incidencia_tecnica'))
    );
    CREATE INDEX IX_notificaciones_usuario_id ON dbo.notificaciones(usuario_id, id);
    CREATE INDEX IX_notificaciones_usuario_estado ON dbo.notificaciones(usuario_id, leida_en, descartada_en, id);
END
GO