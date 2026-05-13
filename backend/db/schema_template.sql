CREATE TABLE IF NOT EXISTS {nombre_tabla} (
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

CREATE INDEX IF NOT EXISTS idx_{nombre_tabla}_job ON {nombre_tabla}(job_id);
CREATE INDEX IF NOT EXISTS idx_{nombre_tabla}_root ON {nombre_tabla}(root_cliente);
