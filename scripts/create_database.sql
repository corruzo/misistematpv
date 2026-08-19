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
        nombre NVARCHAR(150) NOT NULL UNIQUE,
        descripcion NVARCHAR(500) NULL,
        estado NVARCHAR(20) NOT NULL DEFAULT 'Activo',
        fecha_creacion DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        gerencia_id INT NOT NULL,
        CONSTRAINT FK_departamentos_gerencias FOREIGN KEY (gerencia_id) REFERENCES dbo.gerencias(id) ON DELETE NO ACTION,
        CONSTRAINT CK_departamentos_estado CHECK (estado IN ('Activo', 'Inactivo'))
    );
END
GO

IF OBJECT_ID('dbo.cargos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.cargos (
        id INT IDENTITY(1,1) PRIMARY KEY,
        nombre NVARCHAR(150) NOT NULL UNIQUE,
        descripcion NVARCHAR(500) NULL,
        estado NVARCHAR(20) NOT NULL DEFAULT 'Activo',
        fecha_creacion DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        departamento_id INT NOT NULL,
        CONSTRAINT FK_cargos_departamentos FOREIGN KEY (departamento_id) REFERENCES dbo.departamentos(id) ON DELETE NO ACTION,
        CONSTRAINT CK_cargos_estado CHECK (estado IN ('Activo', 'Inactivo'))
    );
END
GO

-- 3) Crear tabla empleados con clave foránea hacia organización
IF OBJECT_ID('dbo.empleados', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.empleados (
        id INT IDENTITY(1,1) PRIMARY KEY,
        cedula NVARCHAR(50) NOT NULL UNIQUE,
        nombre_apellido NVARCHAR(200) NOT NULL,
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
        CONSTRAINT CK_marcajes_asistencia_origen CHECK (origen IN ('PUERTO_COM', 'MANUAL_ADMIN', 'SIMULADOR_DEV'))
    );
    CREATE INDEX IX_marcajes_asistencia_empleado_fecha ON dbo.marcajes_asistencia(empleado_id, fecha_hora DESC);
END
GO

-- 4) Usuarios del sistema (rol único inicial: Administrador)
IF OBJECT_ID('dbo.usuarios', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.usuarios (
        id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(50) NOT NULL UNIQUE,
        nombre NVARCHAR(150) NOT NULL,
        password_hash NVARCHAR(500) NOT NULL,
        rol NVARCHAR(30) NOT NULL DEFAULT 'Administrador',
        activo BIT NOT NULL DEFAULT 1,
        fecha_creacion DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        ultimo_acceso DATETIME2 NULL,
        CONSTRAINT CK_usuarios_rol CHECK (rol = 'Administrador')
    );
END
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