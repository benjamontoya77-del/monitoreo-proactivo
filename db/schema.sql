-- =========================================================================
-- SISTEMA DE MONITOREO PROACTIVO Y ALERTA TEMPRANA  |  PostgreSQL 17
-- Esquema del Hito 2 (6 tablas) + tabla auditoria_acceso (módulo Administración,
-- "Auditoría de Acceso" de la EDT) + columnas necesarias para HTTP/S, SNMP y uptime.
-- Se ejecuta automáticamente la primera vez que arranca el contenedor de la BD.
-- =========================================================================
DROP TABLE IF EXISTS auditoria_acceso CASCADE;
DROP TABLE IF EXISTS alerta_log CASCADE;
DROP TABLE IF EXISTS metrica_historico CASCADE;
DROP TABLE IF EXISTS regla_umbral CASCADE;
DROP TABLE IF EXISTS dispositivo CASCADE;
DROP TABLE IF EXISTS usuario CASCADE;
DROP TABLE IF EXISTS rol CASCADE;

CREATE TABLE rol (
    id SERIAL PRIMARY KEY,
    nombre_rol VARCHAR(100) NOT NULL UNIQUE,
    permisos VARCHAR(255)[] NOT NULL
);

CREATE TABLE usuario (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol_id INT NOT NULL REFERENCES rol(id) ON DELETE RESTRICT,
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE dispositivo (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    ip VARCHAR(15) NOT NULL UNIQUE,
    tipo_dispositivo VARCHAR(50) NOT NULL,
    comunidad_snmp VARCHAR(255) DEFAULT 'public',
    snmp_habilitado BOOLEAN DEFAULT FALSE,          -- NUEVO: SNMP es opcional por nodo
    url_http VARCHAR(500),                          -- NUEVO: chequeo HTTP/S (Hito 1/2)
    frecuencia_segundos INT DEFAULT 60 CHECK (frecuencia_segundos >= 5),
    estado_actual VARCHAR(50) DEFAULT 'ACTIVO'      -- ACTIVO | ALERTA | CRÍTICO
);

CREATE TABLE regla_umbral (
    id SERIAL PRIMARY KEY,
    dispositivo_id INT NOT NULL REFERENCES dispositivo(id) ON DELETE CASCADE,
    parametro VARCHAR(100) NOT NULL,   -- latencia_ms | uso_cpu_pct | uso_ram_pct | interfaces_down | disponibilidad
    valor_umbral FLOAT NOT NULL,
    criticidad VARCHAR(50) NOT NULL,   -- 'Alta' | 'Crítica'
    habilitada BOOLEAN DEFAULT TRUE
);

CREATE TABLE metrica_historico (
    id BIGSERIAL PRIMARY KEY,
    dispositivo_id INT NOT NULL REFERENCES dispositivo(id) ON DELETE CASCADE,
    latencia_ms INT,
    uso_cpu_pct FLOAT,
    uso_ram_pct FLOAT,
    interfaces_down INT,               -- NUEVO: SNMP ifOperStatus
    http_status INT,                   -- NUEVO: código HTTP
    disponible BOOLEAN NOT NULL DEFAULT TRUE,  -- NUEVO: base del cálculo de Uptime/SLA
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_metrica_dispositivo_time ON metrica_historico(dispositivo_id, timestamp DESC);

CREATE TABLE alerta_log (
    id SERIAL PRIMARY KEY,
    dispositivo_id INT NOT NULL REFERENCES dispositivo(id) ON DELETE CASCADE,
    regla_id INT NOT NULL REFERENCES regla_umbral(id) ON DELETE CASCADE,
    descripcion VARCHAR(255) NOT NULL,
    fecha_hora_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_hora_resolucion TIMESTAMP NULL,
    estado_alerta VARCHAR(50) DEFAULT 'ABIERTA'    -- ABIERTA | RESUELTA
);
CREATE INDEX idx_alerta_estado ON alerta_log(estado_alerta, dispositivo_id);

CREATE TABLE auditoria_acceso (
    id BIGSERIAL PRIMARY KEY,
    usuario_id INT REFERENCES usuario(id) ON DELETE SET NULL,
    username VARCHAR(100),
    accion VARCHAR(50) NOT NULL,
    detalle VARCHAR(500),
    ip_origen VARCHAR(64),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Roles (RBAC). Los usuarios se crean desde la aplicación (ver ADMIN_* en .env),
-- nunca con hashes escritos a mano en el SQL.
INSERT INTO rol (nombre_rol, permisos) VALUES
('Administrador TI', ARRAY['CRUD_NODOS','CONFIG_UMBRALES','VER_DASHBOARD','GESTIONAR_ALERTAS','VER_REPORTES','GESTIONAR_USUARIOS']),
('Equipo Tecnico',   ARRAY['VER_DASHBOARD','GESTIONAR_ALERTAS','VER_REPORTES']);
