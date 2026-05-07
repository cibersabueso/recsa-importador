-- Crea las bases de datos por país de RECSA si no existen.
-- Postgres no soporta CREATE DATABASE IF NOT EXISTS de forma directa, por
-- lo que se usa el patrón SELECT ... \gexec, que debe ejecutarse desde psql
-- (no funciona desde un cliente normal: \gexec es un meta-comando de psql).
--
-- Ejecutar desde fuera del contenedor:
--   docker exec -i <contenedor_postgres> psql -U recsa -d postgres < backend/db/create_databases.sql
-- O dentro del contenedor:
--   psql -U recsa -d postgres -f /ruta/al/repo/backend/db/create_databases.sql
--
-- Después de crear las BDs, aplicar el schema con:
--   python -m db.init_db --todos

SELECT 'CREATE DATABASE recsa_cargas'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'recsa_cargas')\gexec

SELECT 'CREATE DATABASE recsa_peru'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'recsa_peru')\gexec

SELECT 'CREATE DATABASE recsa_chile'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'recsa_chile')\gexec

SELECT 'CREATE DATABASE recsa_colombia'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'recsa_colombia')\gexec

SELECT 'CREATE DATABASE recsa_argentina'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'recsa_argentina')\gexec
