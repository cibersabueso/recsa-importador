CREATE TABLE IF NOT EXISTS cargas (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    root_cliente VARCHAR(50),
    nombre_completo VARCHAR(200),
    direccion TEXT,
    telefono_principal VARCHAR(30),
    telefono_secundario VARCHAR(30),
    email VARCHAR(150),
    monto_deuda_original NUMERIC(15,2),
    monto_deuda_actual NUMERIC(15,2),
    fecha_vencimiento DATE,
    numero_documento VARCHAR(100),
    producto VARCHAR(100),
    sucursal_origen VARCHAR(100),
    dias_mora INTEGER,
    tramo_mora VARCHAR(50),
    fecha_carga TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cargas_job ON cargas(job_id);
CREATE INDEX IF NOT EXISTS idx_cargas_root ON cargas(root_cliente);

CREATE TABLE IF NOT EXISTS cargas_jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    empresa VARCHAR(100),
    tipo_carga VARCHAR(50),
    tipo_proceso VARCHAR(50),
    nombre_interfaz VARCHAR(200),
    responsable VARCHAR(100),
    grupo_prueba VARCHAR(50),
    estado VARCHAR(20) NOT NULL,
    iniciado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    terminado_en TIMESTAMP,
    duracion_segundos INTEGER,
    total_filas INTEGER DEFAULT 0,
    filas_validas INTEGER DEFAULT 0,
    filas_con_error INTEGER DEFAULT 0,
    duplicados INTEGER DEFAULT 0,
    sin_match INTEGER DEFAULT 0,
    archivos_procesados JSONB,
    error_mensaje TEXT,
    config_path TEXT
);

ALTER TABLE cargas_jobs ADD COLUMN IF NOT EXISTS grupo_prueba VARCHAR(50);
ALTER TABLE cargas_jobs ADD COLUMN IF NOT EXISTS sin_match INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_jobs_iniciado ON cargas_jobs(iniciado_en DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_estado ON cargas_jobs(estado);
CREATE INDEX IF NOT EXISTS idx_jobs_grupo ON cargas_jobs(grupo_prueba);

DROP VIEW IF EXISTS vista_jobs_por_grupo;
CREATE OR REPLACE VIEW vista_jobs_por_grupo AS
SELECT
    grupo_prueba,
    COUNT(*) AS jobs,
    SUM(total_filas) AS total_filas,
    SUM(filas_validas) AS total_validas,
    SUM(filas_con_error) AS total_errores,
    SUM(duplicados) AS total_duplicados,
    SUM(sin_match) AS total_sin_match,
    AVG(duracion_segundos)::INTEGER AS duracion_promedio_seg,
    MIN(iniciado_en) AS primer_job,
    MAX(iniciado_en) AS ultimo_job
FROM cargas_jobs
WHERE estado = 'completado'
GROUP BY grupo_prueba
ORDER BY ultimo_job DESC;
