# RECSA Cargas — API REST

Contrato HTTP del motor Python/FastAPI consumido por Laravel/Dante. Todos los
endpoints devuelven JSON salvo `GET /api/jobs/{id}/log` (text/plain) y
`GET /api/jobs/{id}/report` (302 a HTML estático).

OpenAPI auto-generada disponible en:
- `GET /docs` — Swagger UI
- `GET /redoc` — ReDoc
- `GET /openapi.json` — JSON crudo

## URL base

| Entorno | URL |
| --- | --- |
| Dev local | `http://localhost:8000` |
| Docker (compose) | `http://recsa-cargas:8000` |
| Stage | (a definir) |

Todos los paths llevan prefijo `/api`.

## Endpoints

| Método | Path | Descripción |
| --- | --- | --- |
| `POST` | `/api/jobs` | Encola un job de procesamiento |
| `GET` | `/api/jobs` | Lista jobs (paginado, filtrable) |
| `GET` | `/api/jobs/{id}` | Estado y metadata de un job |
| `GET` | `/api/jobs/{id}/log` | Log del job en texto plano |
| `GET` | `/api/jobs/{id}/report` | Redirect 302 al HTML del reporte |
| `GET` | `/api/health` | Health check (Redis + BDs por país) |

Endpoints legacy (deprecados pero funcionales):

| Método | Path | Notas |
| --- | --- | --- |
| `POST` | `/api/procesar` | Encola job vía contrato del frontend Angular |
| `GET` | `/api/resultado/{id}` | Estado del job vía Redis |
| `POST` | `/api/queue/enqueue` | Encolado simple sin Postgres |
| `GET` | `/api/queue/jobs` | Listado desde Redis |

## Estados de un job

| Estado | Significado |
| --- | --- |
| `encolado` | Job aceptado, esperando worker libre |
| `procesando` | Un worker tomó el job y lo está ejecutando |
| `completado` | Terminó OK; reporte HTML disponible |
| `error` | Terminó con error de datos (filas inválidas, columnas faltantes, etc.) |
| `fallido` | Crash del worker; el job se movió a `recsa:queue:failed` para auditoría |

`error` indica problema en los datos del job; `fallido` indica problema del
motor (excepción no controlada). Ambos son terminales.

---

## `POST /api/jobs`

Encola un nuevo job. Misma estructura que los YAML de `backend/cli/configs/`.

### Request body

```json
{
  "proceso": {
    "empresa": "MOVISTAR_CL",
    "pais": "CHILE",
    "tipo_carga": "ASIGNACION",
    "tipo_proceso": "INICIAL",
    "nombre_interfaz": "Movistar full",
    "responsable": "dante.api",
    "grupo_prueba": "movistar_v3"
  },
  "archivos": [
    {
      "layout": "movistar_documentos",
      "ruta": "/data/movistar/DOCUMENTOS_SCRECSA_20260305.txt",
      "orden": 1,
      "columna_clave": "numero_documento",
      "columna_join": "root_cliente",
      "mapeos": [
        { "origen": "NUM_FOLIO", "destino": "numero_documento", "obligatorio": true },
        { "origen": "NUM_IDENT", "destino": "root_cliente", "obligatorio": true },
        { "origen": "FEC_VENC", "destino": "fecha_vencimiento", "obligatorio": true },
        { "origen": "IMPORTE", "destino": "monto_deuda_original", "obligatorio": true }
      ]
    },
    {
      "layout": "movistar_contacto",
      "ruta": "/data/movistar/CONTACTO_SCRECSA_20260305.txt",
      "orden": 2,
      "columna_clave": "root_cliente",
      "mapeos": [
        { "origen": "NUM_IDENT", "destino": "root_cliente", "obligatorio": true },
        { "origen": "NOM_CLIENTE", "destino": "nombre_completo" },
        { "origen": "TEL_CONTACTO", "destino": "telefono_principal" },
        { "origen": "EMAIL", "destino": "email" }
      ]
    }
  ]
}
```

Campos clave:
- `proceso.empresa`: nombre del cliente. Define la **tabla de precarga aislada
  por cliente**: cada empresa escribe a su propia tabla `cargas_<empresa
  normalizada>` dentro de la BD del país, evitando contención entre clientes
  que cargan en simultáneo (ver sección "Persistencia multi-cliente").
- `proceso.pais` (opcional): código del país (PERU/CHILE/COLOMBIA/ARGENTINA).
  Resuelve la BD destino. Si se omite, cae a `recsa_cargas` (default).
- `proceso.grupo_prueba` (opcional): etiqueta para agrupar jobs (`movistar_v3`,
  `recsa_peru_v2`, etc.) y comparar tiempos vía la vista `vista_jobs_por_grupo`.
- `archivos[].layout`: nombre del layout YAML en `backend/cli/layouts/`. Define
  delimitador, codificación, encabezados y columnas declaradas.
- `archivos[].ruta`: path absoluto al archivo en el filesystem visible al
  worker (montado vía Docker volume o SFTP previo).
- `archivos[].columna_clave`: identidad única por fila del principal
  (orden=1) o de cruce en secundarios.
- `archivos[].columna_join` (opcional): si difiere de `columna_clave`, se usa
  para cruzar 1:N con secundarios (ej: una factura tiene N teléfonos).

Límites del payload:
- **Máximo 200 mapeos sumados entre todos los archivos** del job. Si el config
  excede este tope, `POST /api/jobs` responde 400 con
  `Límite de columnas excedido: <N> > 200`. El límite vale por tabla destino;
  como hoy todos los mapeos terminan en la misma tabla del cliente, se cuenta
  el total agregado.

### Response — 202 Accepted

```json
{
  "jobId": "a1b2c3d4e5f6...",
  "estado": "encolado",
  "pais": "CHILE",
  "consultarEn": "/api/jobs/a1b2c3d4e5f6..."
}
```

### Errores

| Código | Causa |
| --- | --- |
| `400` | Payload inválido (layout no existe, falta `columna_clave`, etc.) |
| `500` | No se pudo encolar (Redis/Postgres caído) |

### Ejemplo curl

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d @movistar_chile.json
```

### Ejemplo body — RECSA Perú

```json
{
  "proceso": {
    "empresa": "RECSA_PERU",
    "pais": "PERU",
    "tipo_carga": "ASIGNACION",
    "tipo_proceso": "INICIAL",
    "nombre_interfaz": "RECSA Peru cartera 20260429",
    "responsable": "dante.api",
    "grupo_prueba": "recsa_peru_v2"
  },
  "archivos": [
    {
      "layout": "recsa_case_assignment",
      "ruta": "/data/recsa_peru/case_assignment_R_RECSA_20260429.txt",
      "orden": 1,
      "columna_clave": "numero_operacion",
      "columna_join": "codigo_cliente_interno",
      "mapeos": [
        { "origen": "numero_operacion", "destino": "numero_documento", "obligatorio": true },
        { "origen": "dni_cliente", "destino": "root_cliente", "obligatorio": true },
        { "origen": "nombre_cliente", "destino": "nombre_completo" },
        { "origen": "monto_actual", "destino": "monto_deuda_actual" },
        { "origen": "fecha_vencimiento", "destino": "fecha_vencimiento" },
        { "origen": "dias_mora", "destino": "dias_mora" },
        { "origen": "tramo", "destino": "tramo_mora" }
      ]
    },
    {
      "layout": "recsa_contact_phone",
      "ruta": "/data/recsa_peru/contact_phone_RECSA_20260429.txt",
      "orden": 2,
      "columna_clave": "codigo_cliente_interno",
      "mapeos": [
        { "origen": "telefono", "destino": "telefono_principal" }
      ]
    }
  ]
}
```

---

## `GET /api/jobs`

Lista jobs paginados, opcionalmente filtrados.

### Query params

| Param | Tipo | Default | Descripción |
| --- | --- | --- | --- |
| `pais` | string | — | Filtra por país. Si se omite, hace fan-out a todas las BDs |
| `grupo` | string | — | Filtra por `grupo_prueba` |
| `estado` | string | — | Filtra por estado (`encolado`/`procesando`/`completado`/`error`/`fallido`) |
| `limit` | int | `50` | Tamaño de página (1–500) |
| `offset` | int | `0` | Desplazamiento de la página |

### Response

```json
{
  "jobs": [
    {
      "job_id": "a1b2c3...",
      "empresa": "MOVISTAR_CL",
      "tipo_carga": "ASIGNACION",
      "tipo_proceso": "INICIAL",
      "nombre_interfaz": "Movistar full",
      "responsable": "dante.api",
      "grupo_prueba": "movistar_v3",
      "estado": "completado",
      "iniciado_en": "2026-05-06T14:21:03.123456",
      "terminado_en": "2026-05-06T14:24:07.456789",
      "duracion_segundos": 184,
      "total_filas": 5234121,
      "filas_validas": 5230002,
      "filas_con_error": 4119,
      "duplicados": 0,
      "sin_match": 0,
      "error_mensaje": null,
      "config_path": "",
      "pais": "CHILE"
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

`iniciado_en` y `terminado_en` son ISO-8601. Si una BD del fan-out está caída,
se omite (se loguea internamente).

### Ejemplo curl

```bash
curl "http://localhost:8000/api/jobs?pais=CHILE&estado=completado&limit=20"
curl "http://localhost:8000/api/jobs?grupo=movistar_v3"
curl "http://localhost:8000/api/jobs"
```

---

## `GET /api/jobs/{id}`

Devuelve el job completo. Busca en todas las BDs hasta encontrarlo.

### Response

Mismos campos que cada item de `GET /api/jobs.jobs[]`. Devuelve `200` o
`404` si el job no existe en ninguna BD configurada.

### Ejemplo curl

```bash
curl http://localhost:8000/api/jobs/a1b2c3d4e5f6
```

---

## `GET /api/jobs/{id}/log`

Devuelve el log estructurado del job (`backend/logs/{job_id}.log`) como
`text/plain`. Útil para debugging desde Laravel sin tener acceso al filesystem.

| Código | Causa |
| --- | --- |
| `200` | Log servido como texto plano |
| `404` | Log no existe (job nunca se ejecutó o fue purgado) |

### Ejemplo curl

```bash
curl http://localhost:8000/api/jobs/a1b2c3/log
```

---

## `GET /api/jobs/{id}/report`

Si existe el reporte HTML del job, redirige (302) a
`/static/reportes/{job_id}.html`. Sino devuelve 404. El HTML se sirve
estáticamente desde `backend/reportes/`.

### Ejemplo curl

```bash
curl -L http://localhost:8000/api/jobs/a1b2c3/report
```

Desde el navegador: `http://localhost:8000/api/jobs/a1b2c3/report`.

---

## `GET /api/health`

Health check del motor.

### Response

```json
{
  "estado": "ok",
  "servicio": "recsa-cargas",
  "redis": "ok",
  "paises": [
    { "pais": "PERU", "db": "recsa_peru", "estado": "ok" },
    { "pais": "CHILE", "db": "recsa_chile", "estado": "ok" },
    { "pais": "COLOMBIA", "db": "recsa_colombia", "estado": "ok" },
    { "pais": "ARGENTINA", "db": "recsa_argentina", "estado": "ok" },
    { "pais": "default", "db": "recsa_cargas", "estado": "ok" }
  ],
  "cola_pendiente": 5,
  "workers_activos": 4,
  "workers_max": 20
}
```

| Campo | Significado |
| --- | --- |
| `redis` | `ok` si el motor pudo hacer `PING` a Redis |
| `paises[]` | Una entrada por BD configurada (`databases.yml`); incluye `{ "estado": "error", "error": "..." }` si la BD está caída |
| `cola_pendiente` | `LLEN recsa:queue:jobs`: jobs encolados que esperan worker |
| `workers_activos` | Cuenta claves `recsa:processing:*` en Redis (un worker ocupado tiene una) |
| `workers_max` | Tope configurado por el supervisor; `null` si el supervisor no está corriendo (o murió y la meta key TTL expiró) |

### Ejemplo curl

```bash
curl http://localhost:8000/api/health
```

---

## Flujo recomendado para Laravel

1. `POST /api/jobs` con el payload del job. Guardar `jobId` devuelto.
2. Polling cada N segundos (o WebSocket Reverb cuando esté disponible) sobre
   `GET /api/jobs/{jobId}` mostrando `estado` y, una vez `procesando`,
   `filas_validas` / `filas_con_error` parciales.
3. Cuando el estado pasa a `completado`:
   - Mostrar resumen con los conteos.
   - Linkear `GET /api/jobs/{jobId}/report` para abrir el HTML en una nueva pestaña.
4. Si el estado pasa a `error` o `fallido`:
   - Mostrar `error_mensaje`.
   - Linkear `GET /api/jobs/{jobId}/log` para que el operador inspeccione el detalle.

## Códigos de error transversales

| Código | Significado |
| --- | --- |
| `400` | Body o query params inválidos (detalle en `detail`) |
| `404` | Job/log/reporte no encontrado |
| `500` | Error inesperado del motor |
| `502/503` | Redis o Postgres no disponibles (`/api/health` lo refleja) |

Las respuestas de error siguen el formato FastAPI:

```json
{ "detail": "Mensaje legible para humanos" }
```

## Layouts disponibles

Los `layout` aceptados por `POST /api/jobs` están en
`backend/cli/layouts/`. Los actuales:

- `movistar_documentos` — DOCUMENTOS_SCRECSA (Chile)
- `movistar_contacto`, `movistar_abonados`, `movistar_gestiones`,
  `movistar_movimientos` — secundarios Movistar
- `recsa_case_assignment` — case_assignment principal RECSA Perú
- `recsa_contact_phone` — teléfonos secundarios RECSA Perú

Para sumar un layout nuevo, agregar el YAML en esa carpeta y referenciarlo por
nombre en `archivos[].layout`. No se puede pasar el layout inline en el JSON
todavía.

---

## Supervisor de workers (paralelismo dinámico)

El motor de procesamiento corre como un **supervisor** que escala workers
dinámicamente según el tamaño de la cola Redis. No hay un número fijo de
workers: si llegan 10 jobs en simultáneo, el supervisor levanta hasta 10
procesos en paralelo; si llegan 20, levanta hasta 20 (o hasta `--max-workers`,
lo que sea menor). Cuando la cola se vacía, los workers idle se mueren solos.

### Levantar el supervisor

```bash
cd backend
python -m cli.worker --max-workers 20
```

Argumentos:

| Argumento | Default | Significado |
| --- | --- | --- |
| `--max-workers` | `20` | Tope máximo de workers concurrentes (techo de seguridad para no saturar Postgres) |
| `--min-workers` | `0` | Cantidad mínima de workers siempre vivos (útil si querés latencia baja en jobs ocasionales) |
| `--check-interval` | `2` | Segundos entre cada chequeo de la cola |
| `--idle-timeout` | `30` | Segundos sin recibir trabajo antes de que un worker termine solo |

### Cómo funciona el escalado

Cada `--check-interval` segundos el supervisor:

1. Lee `LLEN recsa:queue:jobs` (cola pendiente).
2. Cuenta workers vivos (procesos hijos `is_alive()`).
3. Decide cuántos nuevos spawnear:
   - `objetivo = clamp(cola, min_workers, max_workers)`
   - `nuevos = max(0, objetivo - vivos)`
4. Si `nuevos > 0`, levanta esa cantidad de workers nuevos.
5. Imprime un status line:

```
[12:03:45] cola=5  workers=3  -> levantando 2 nuevos
[12:03:47] cola=0  workers=4  -> idle
[12:03:49] cola=0  workers=2  -> idle
[12:03:51] cola=20 workers=2  -> levantando 18 nuevos
[12:03:53] cola=12 workers=20 -> saturado
```

Estados posibles:

| Estado | Significado |
| --- | --- |
| `levantando N nuevos` | Acaba de spawnear N workers para responder a demanda |
| `idle` | Cola vacía; los workers idle se mueren cuando llegan a su `idle-timeout` |
| `estable` | Hay jobs en cola pero los workers vivos los van a tomar; no hace falta más |
| `saturado` | Llegó al techo `--max-workers`; los jobs sobrantes esperan turno |

### Auto-muerte de workers idle

Cada worker hijo lleva su propio reloj de inactividad. Si después de
`--idle-timeout` segundos no agarró ningún job, sale limpiamente (drena su
`recsa:processing:{pid}` reencolando jobs huérfanos, cierra la conexión a
Redis y muere). El supervisor **no mata workers manualmente** durante
operación normal; los idle se auto-terminan. Esto es más robusto que matar
procesos a la fuerza con `terminate()`.

### Apagado limpio

`Ctrl+C` (SIGINT) o `kill <pid>` (SIGTERM) sobre el supervisor:

1. Notifica a todos los workers vivos vía SIGTERM.
2. Cada worker termina su job actual (no interrumpe procesamiento) y sale.
3. El supervisor espera hasta 30 segundos a que todos terminen.
4. Si alguno queda colgado, lo mata con `terminate()` y reencola sus jobs
   huérfanos a `recsa:queue:jobs` para que la próxima ronda los retome.
5. Limpia la meta-key `recsa:supervisor:meta` y se cierra.

### Visibilidad desde el frontend

`GET /api/health` expone `cola_pendiente`, `workers_activos` y `workers_max`
para que Dante muestre en tiempo real cuántos jobs están esperando y cuántos
motores están procesando. Ver la sección de health más arriba.

---

## Persistencia multi-cliente

Cada cliente (mandante) tiene su propia tabla de precarga dentro de la BD del
país. Si Movistar y otra empresa cargan al mismo tiempo en Chile, escriben a
tablas distintas y no se pelean por locks.

### Convención de nombre de tabla

`cargas_<empresa normalizada>`. La normalización pasa el `proceso.empresa` a
lowercase, le saca tildes/ñ y reemplaza caracteres fuera de `[a-z0-9_]` por
`_`. Ejemplos:

| `proceso.empresa` | Tabla destino |
| --- | --- |
| `MOVISTAR_CL` | `cargas_movistar_cl` |
| `RECSA_PERU` | `cargas_recsa_peru` |
| `BANCO FRANCES` | `cargas_banco_frances` |
| `Banco Francés` | `cargas_banco_frances` |

Postgres limita los identificadores a 63 caracteres. Si el nombre supera 60
caracteres, se trunca a 50 y se le agrega `_` + los primeros 8 caracteres del
MD5 del nombre original para evitar colisiones entre empresas con prefijos
largos compartidos.

### Ciclo de vida de las tablas

- Las tablas `cargas_<cliente>` se crean **on-demand** al procesar el primer
  job de cada cliente (vía `CREATE TABLE IF NOT EXISTS`). `python -m db.init_db`
  solo crea `cargas_jobs` (metadatos); no toca las tablas por cliente.
- Después de crear/asegurar la tabla, el motor regenera la vista
  `cargas_unificada` (DROP + CREATE) con `UNION ALL` de todas las tablas
  `cargas_*` actuales y una columna extra `tabla_origen` (el sufijo sin
  prefijo). Esta vista alimenta los reportes globales y permite consultas
  cross-cliente.

### Consulta cross-cliente

```sql
SELECT tabla_origen, COUNT(*) AS filas, COUNT(DISTINCT job_id) AS jobs
FROM cargas_unificada
GROUP BY tabla_origen
ORDER BY filas DESC;
```

Si todavía no se procesó ningún job, `cargas_unificada` no existe y la query
levanta `UndefinedTable`. El reporte HTML por job atrapa el error y devuelve
muestra/calidad vacías para que el render no crashee.
