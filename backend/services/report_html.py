from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg import Connection

from models.job import JobPayload
from models.resultado import EstadisticasArchivo, ResultadoProceso
from services.progress_tracker import FaseRegistro

REPORTES_DIR: Path = Path(__file__).resolve().parent.parent / "reportes"

CAMPOS_CALIDAD: tuple[tuple[str, str], ...] = (
    ("con_root", "root_cliente"),
    ("con_nombre", "nombre_completo"),
    ("con_telefono", "telefono_principal"),
    ("con_email", "email"),
    ("con_direccion", "direccion"),
    ("con_monto", "monto_deuda_actual"),
    ("con_fecha", "fecha_vencimiento"),
)

COLUMNAS_MUESTRA: tuple[str, ...] = (
    "root_cliente",
    "nombre_completo",
    "telefono_principal",
    "monto_deuda_actual",
    "fecha_vencimiento",
    "numero_documento",
)

PALETA_FASES: tuple[str, ...] = (
    "#1e3a8a",
    "#2563eb",
    "#3b82f6",
    "#0ea5e9",
    "#06b6d4",
    "#10b981",
    "#84cc16",
    "#f59e0b",
    "#ef4444",
    "#a855f7",
)


def consultar_calidad_datos(conn: Connection, job_id: str) -> dict[str, int]:
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE root_cliente IS NOT NULL) AS con_root,
            COUNT(*) FILTER (WHERE nombre_completo IS NOT NULL) AS con_nombre,
            COUNT(*) FILTER (WHERE telefono_principal IS NOT NULL) AS con_telefono,
            COUNT(*) FILTER (WHERE email IS NOT NULL) AS con_email,
            COUNT(*) FILTER (WHERE direccion IS NOT NULL) AS con_direccion,
            COUNT(*) FILTER (WHERE monto_deuda_actual IS NOT NULL) AS con_monto,
            COUNT(*) FILTER (WHERE fecha_vencimiento IS NOT NULL) AS con_fecha,
            COUNT(*) AS total
        FROM cargas
        WHERE job_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (job_id,))
        row = cur.fetchone()
    if row is None:
        return {clave: 0 for clave, _ in CAMPOS_CALIDAD} | {"total": 0}
    keys = [clave for clave, _ in CAMPOS_CALIDAD] + ["total"]
    return dict(zip(keys, [int(v or 0) for v in row]))


def consultar_muestra(
    conn: Connection, job_id: str, limite: int = 20
) -> list[dict[str, Any]]:
    columnas_sql = ", ".join(COLUMNAS_MUESTRA)
    sql = (
        f"SELECT {columnas_sql} FROM cargas WHERE job_id = %s "
        "ORDER BY id ASC LIMIT %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (job_id, limite))
        rows = cur.fetchall()
    return [dict(zip(COLUMNAS_MUESTRA, fila)) for fila in rows]


def _formato_mmss(segundos: float) -> str:
    if segundos < 60:
        return f"{int(segundos)}s"
    minutos = int(segundos // 60)
    seg = int(segundos % 60)
    if minutos < 60:
        return f"{minutos}m {seg:02d}s"
    horas = minutos // 60
    minutos = minutos % 60
    return f"{horas}h {minutos:02d}m {seg:02d}s"


def _formato_bytes(bytes_: int) -> str:
    valor = float(bytes_)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidad == "TB":
            return f"{valor:.2f} {unidad}"
        valor /= 1024
    return f"{valor:.2f} TB"


def _porcentaje(parte: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return 100.0 * parte / total


def _clase_calidad(porcentaje: float) -> str:
    if porcentaje >= 75.0:
        return "high"
    if porcentaje >= 40.0:
        return "medium"
    return "low"


def _esc(valor: Any) -> str:
    if valor is None:
        return ""
    return html.escape(str(valor), quote=True)


def _render_header(
    job_id: str,
    payload: JobPayload,
    resultado: ResultadoProceso,
    fases: list[FaseRegistro],
    grupo_prueba: str | None,
    pais: str | None,
) -> str:
    proceso = payload.proceso
    inicio = fases[0].inicio if fases else None
    fin = fases[-1].fin if fases else None
    duracion = sum(f.duracion_segundos for f in fases)
    estado_clase = "badge-ok" if resultado.estado == "completado" else "badge-error"
    estado_texto = (
        "COMPLETADO" if resultado.estado == "completado" else resultado.estado.upper()
    )
    inicio_str = inicio.strftime("%Y-%m-%d %H:%M:%S") if inicio else "-"
    fin_str = fin.strftime("%Y-%m-%d %H:%M:%S") if fin else "-"
    grupo_str = grupo_prueba or "-"
    pais_str = pais.strip().upper() if pais else "-"
    subtitulo = (
        f'<div class="subtitulo">País: <strong>{_esc(pais_str)}</strong></div>'
    )
    errores_html = ""
    if resultado.estado == "error" and resultado.errores:
        items = "".join(f"<li>{_esc(err)}</li>" for err in resultado.errores)
        errores_html = f"""
  <div class="errores-rechazo">
    <strong>Carga rechazada. Errores detectados:</strong>
    <ul>{items}</ul>
  </div>
"""
    return f"""
<header>
  <h1>Reporte de Carga: {_esc(proceso.empresa)} - {_esc(proceso.nombre_interfaz)}</h1>
  {subtitulo}
  <div class="meta">
    <div><strong>Job ID:</strong> <code>{_esc(job_id)}</code></div>
    <div><strong>País:</strong> {_esc(pais_str)}</div>
    <div><strong>Grupo de prueba:</strong> {_esc(grupo_str)}</div>
    <div><strong>Responsable:</strong> {_esc(proceso.responsable)}</div>
    <div><strong>Inicio:</strong> {_esc(inicio_str)}</div>
    <div><strong>Fin:</strong> {_esc(fin_str)}</div>
    <div><strong>Duración total:</strong> {_esc(_formato_mmss(duracion))}</div>
    <div><strong>Tipo de carga:</strong> {_esc(proceso.tipo_carga)}</div>
    <div><strong>Tipo de proceso:</strong> {_esc(proceso.tipo_proceso)}</div>
  </div>
  <div style="margin-top:1rem;">
    <span class="badge {estado_clase}">{_esc(estado_texto)}</span>
  </div>
  {errores_html}
</header>
"""


def _render_resumen(resultado: ResultadoProceso) -> str:
    err_clase = "yellow" if resultado.filas_con_error > 0 else "gray"
    dup_clase = "yellow" if resultado.duplicados > 0 else "gray"
    sm_clase = "yellow" if resultado.sin_match > 0 else "gray"
    return f"""
<section>
  <h2>Resumen ejecutivo</h2>
  <div class="cards cards-5">
    <div class="card">
      <div class="label">Total leídas</div>
      <div class="value">{resultado.total_filas:,}</div>
    </div>
    <div class="card green">
      <div class="label">Filas válidas</div>
      <div class="value">{resultado.filas_validas:,}</div>
    </div>
    <div class="card {err_clase}">
      <div class="label">Filas con error</div>
      <div class="value">{resultado.filas_con_error:,}</div>
    </div>
    <div class="card {dup_clase}">
      <div class="label">Duplicados</div>
      <div class="value">{resultado.duplicados:,}</div>
    </div>
    <div class="card {sm_clase}">
      <div class="label">Sin match</div>
      <div class="value">{resultado.sin_match:,}</div>
    </div>
  </div>
</section>
"""


def _render_calidad(calidad: dict[str, int] | None) -> str:
    if not calidad:
        return ""
    total = int(calidad.get("total", 0) or 0)
    filas: list[str] = []
    for clave, etiqueta in CAMPOS_CALIDAD:
        cantidad = int(calidad.get(clave, 0) or 0)
        pct = _porcentaje(cantidad, total)
        clase = _clase_calidad(pct)
        filas.append(
            f"""
        <div class="quality-row">
          <div class="quality-label">{_esc(etiqueta)}</div>
          <div class="quality-count">{cantidad:,}</div>
          <div class="quality-pct">{pct:.1f}%</div>
          <div class="quality-bar">
            <div class="quality-fill {clase}" style="width: {pct:.1f}%;"></div>
          </div>
        </div>
"""
        )
    cuerpo = "".join(filas)
    return f"""
<section>
  <h2>Calidad de datos</h2>
  <p class="muted">Cobertura por campo sobre {total:,} filas insertadas en Postgres.</p>
  {cuerpo}
</section>
"""


def _render_timeline(fases: list[FaseRegistro]) -> str:
    if not fases:
        return ""
    labels = [f.nombre for f in fases]
    duraciones = [round(f.duracion_segundos, 2) for f in fases]
    colores = [PALETA_FASES[i % len(PALETA_FASES)] for i in range(len(fases))]
    etiquetas_duracion = [_formato_mmss(f.duracion_segundos) for f in fases]
    data = {
        "labels": labels,
        "duraciones": duraciones,
        "colores": colores,
        "etiquetas": etiquetas_duracion,
    }
    data_json = json.dumps(data, ensure_ascii=False)
    return f"""
<section>
  <h2>Línea de tiempo del proceso</h2>
  <div class="chart-container">
    <canvas id="timelineChart"></canvas>
  </div>
  <script>
    (function() {{
      const data = {data_json};
      const ctx = document.getElementById('timelineChart');
      new Chart(ctx, {{
        type: 'bar',
        data: {{
          labels: data.labels,
          datasets: [{{
            label: 'Duración',
            data: data.duraciones,
            backgroundColor: data.colores,
            borderRadius: 4
          }}]
        }},
        options: {{
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              callbacks: {{
                label: function(ctx) {{
                  return data.etiquetas[ctx.dataIndex];
                }}
              }}
            }}
          }},
          scales: {{
            x: {{
              title: {{ display: true, text: 'Segundos' }},
              beginAtZero: true
            }}
          }}
        }}
      }});
    }})();
  </script>
</section>
"""


def _tamano_archivo(ruta: str) -> int:
    try:
        return Path(ruta).stat().st_size
    except OSError:
        return 0


def _fase_por_archivo(
    fases: list[FaseRegistro], nombre_archivo: str
) -> FaseRegistro | None:
    for fase in fases:
        if nombre_archivo in fase.nombre:
            return fase
    return None


def _render_archivos(
    payload: JobPayload,
    estadisticas: list[EstadisticasArchivo],
    fases: list[FaseRegistro],
) -> str:
    if not estadisticas:
        return ""
    archivos_por_id = {a.archivo_id: a for a in payload.archivos}
    filas: list[str] = []
    for stats in sorted(estadisticas, key=lambda e: e.orden):
        archivo = archivos_por_id.get(stats.archivo_id)
        if archivo is None:
            continue
        tamano = _tamano_archivo(archivo.ruta)
        fase = _fase_por_archivo(fases, archivo.nombre)
        duracion = (
            _formato_mmss(fase.duracion_segundos) if fase is not None else "-"
        )
        velocidad = "-"
        if fase is not None and fase.duracion_segundos > 0:
            vps = stats.total_filas / fase.duracion_segundos
            velocidad = f"{vps:,.0f}/s"
        layout_nombre = "-"
        if "_" in archivo.nombre.lower():
            base = Path(archivo.nombre).stem.lower()
            layout_nombre = base
        filas.append(
            f"""
      <tr>
        <td>{stats.orden}</td>
        <td>{_esc(archivo.nombre)}</td>
        <td><code>{_esc(archivo.tipo)}</code></td>
        <td class="num">{_formato_bytes(tamano)}</td>
        <td class="num">{stats.total_filas:,}</td>
        <td class="num">{stats.filas_validas:,}</td>
        <td class="num">{stats.filas_con_error:,}</td>
        <td class="num">{stats.duplicados:,}</td>
        <td class="num">{stats.sin_match:,}</td>
        <td class="num">{duracion}</td>
        <td class="num">{velocidad}</td>
      </tr>
"""
        )
    cuerpo = "".join(filas)
    return f"""
<section>
  <h2>Archivos procesados</h2>
  <table>
    <thead>
      <tr>
        <th>Orden</th>
        <th>Nombre</th>
        <th>Tipo</th>
        <th class="num">Tamaño</th>
        <th class="num">Leídas</th>
        <th class="num">Válidas</th>
        <th class="num">Errores</th>
        <th class="num">Duplicados</th>
        <th class="num">Sin match</th>
        <th class="num">Duración</th>
        <th class="num">Velocidad</th>
      </tr>
    </thead>
    <tbody>
      {cuerpo}
    </tbody>
  </table>
  <p class="leyenda muted">
    <strong>Duplicados:</strong> filas con clave identidad repetida descartadas.
    <strong>Sin match:</strong> filas de secundarios cuya clave no existe en el archivo principal.
  </p>
</section>
"""


def _render_muestra(datos: list[dict[str, Any]]) -> str:
    if not datos:
        return ""
    filas: list[str] = []
    for fila in datos:
        celdas = "".join(
            f"<td>{_esc(fila.get(col))}</td>" for col in COLUMNAS_MUESTRA
        )
        filas.append(f"<tr>{celdas}</tr>")
    cuerpo = "".join(filas)
    encabezados = "".join(f"<th>{_esc(c)}</th>" for c in COLUMNAS_MUESTRA)
    return f"""
<section>
  <h2>Muestra de datos generados</h2>
  <p class="muted">Primeras {len(datos)} filas insertadas en <code>cargas</code>.</p>
  <div class="tabla-scroll">
    <table>
      <thead><tr>{encabezados}</tr></thead>
      <tbody>{cuerpo}</tbody>
    </table>
  </div>
</section>
"""


def _render_footer(job_id: str) -> str:
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""
<footer>
  <div>Generado por motor RECSA Cargas v1.0</div>
  <div>Log del job: <code>backend/logs/{_esc(job_id)}.log</code></div>
  <div>Generado el: {_esc(ahora)}</div>
</footer>
"""


_CSS_TEMPLATE: str = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  background: #f3f4f6;
  color: #111827;
  line-height: 1.55;
  padding: 2rem 1rem;
}
.container { max-width: 1200px; margin: 0 auto; }
header {
  background: #ffffff;
  padding: 1.75rem 2rem;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  margin-bottom: 1.5rem;
  border-left: 6px solid #1e3a8a;
}
header h1 { color: #1e3a8a; font-size: 1.625rem; margin-bottom: 0.5rem; }
header .subtitulo { color: #4b5563; font-size: 0.95rem; margin-bottom: 0.25rem; }
header .subtitulo strong { color: #1e3a8a; font-weight: 700; letter-spacing: 0.04em; }
header .meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.5rem 1.5rem;
  color: #4b5563;
  font-size: 0.9rem;
  margin-top: 0.75rem;
}
header .meta strong { color: #1f2937; font-weight: 600; }
code { font-family: "SFMono-Regular", Consolas, Menlo, monospace; font-size: 0.85em; background: #f3f4f6; padding: 0.1rem 0.35rem; border-radius: 4px; }
.badge {
  display: inline-block;
  padding: 0.3rem 0.85rem;
  border-radius: 9999px;
  font-weight: 600;
  font-size: 0.85rem;
  letter-spacing: 0.04em;
}
.badge-ok { background: #dcfce7; color: #16a34a; }
.badge-error { background: #fee2e2; color: #dc2626; }
.errores-rechazo {
  background: #fee2e2;
  border-left: 4px solid #dc2626;
  padding: 1rem 1.25rem;
  margin-top: 1rem;
  border-radius: 0.4rem;
  color: #7f1d1d;
}
.errores-rechazo strong { color: #991b1b; display: block; margin-bottom: 0.4rem; }
.errores-rechazo ul { padding-left: 1.5rem; line-height: 1.7; }
.errores-rechazo li { margin-bottom: 0.25rem; }
section {
  background: #ffffff;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  padding: 1.5rem 1.75rem;
  margin-bottom: 1.5rem;
}
section h2 {
  color: #1e3a8a;
  font-size: 1.15rem;
  margin-bottom: 1rem;
  padding-bottom: 0.65rem;
  border-bottom: 1px solid #e5e7eb;
}
.muted { color: #6b7280; font-size: 0.875rem; margin-bottom: 0.75rem; }
.cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}
.cards.cards-5 { grid-template-columns: repeat(5, 1fr); }
.leyenda { margin-top: 0.85rem; }
.leyenda strong { color: #1f2937; }
.card {
  background: #f9fafb;
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  text-align: left;
  border-left: 4px solid #d1d5db;
}
.card.green { border-color: #16a34a; }
.card.yellow { border-color: #f59e0b; }
.card.gray { border-color: #6b7280; }
.card .label {
  color: #6b7280;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.card .value {
  font-size: 1.875rem;
  font-weight: 700;
  color: #111827;
  margin-top: 0.4rem;
}
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td {
  text-align: left;
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid #e5e7eb;
}
th {
  background: #f3f4f6;
  font-weight: 600;
  color: #374151;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
th.num, td.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr:nth-child(even) { background: #f9fafb; }
.tabla-scroll { overflow-x: auto; }
.quality-row {
  display: grid;
  grid-template-columns: 220px 100px 80px 1fr;
  gap: 1rem;
  align-items: center;
  padding: 0.55rem 0;
  border-bottom: 1px solid #f3f4f6;
}
.quality-row:last-child { border-bottom: none; }
.quality-label { font-weight: 500; color: #1f2937; }
.quality-count { font-variant-numeric: tabular-nums; color: #4b5563; }
.quality-pct { font-variant-numeric: tabular-nums; font-weight: 600; color: #111827; }
.quality-bar {
  height: 12px;
  background: #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}
.quality-fill { height: 100%; transition: width 0.3s ease; border-radius: 6px; }
.quality-fill.high { background: linear-gradient(90deg, #16a34a, #22c55e); }
.quality-fill.medium { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.quality-fill.low { background: linear-gradient(90deg, #dc2626, #f87171); }
.chart-container {
  position: relative;
  height: 360px;
  margin-top: 0.5rem;
}
footer {
  margin-top: 2rem;
  padding: 1.25rem 1.5rem;
  border-top: 1px solid #e5e7eb;
  color: #6b7280;
  font-size: 0.85rem;
  text-align: center;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}
@media (max-width: 1100px) { .cards.cards-5 { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .cards { grid-template-columns: 1fr 1fr; } .cards.cards-5 { grid-template-columns: 1fr 1fr; } }
@media (max-width: 540px) { .cards { grid-template-columns: 1fr; } .cards.cards-5 { grid-template-columns: 1fr; } .quality-row { grid-template-columns: 1fr; gap: 0.25rem; } }
"""


def generar_reporte_html(
    job_id: str,
    payload: JobPayload,
    resultado: ResultadoProceso,
    fases: list[FaseRegistro],
    datos_muestra: list[dict[str, Any]],
    calidad: dict[str, int] | None = None,
    grupo_prueba: str | None = None,
    pais: str | None = None,
    ruta_salida: Path | None = None,
) -> Path:
    if ruta_salida is None:
        ruta_salida = REPORTES_DIR / f"{job_id}.html"
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    titulo = f"Reporte de Carga - {payload.proceso.empresa} - {payload.proceso.nombre_interfaz}"

    cuerpo = (
        _render_header(job_id, payload, resultado, fases, grupo_prueba, pais)
        + _render_resumen(resultado)
        + _render_calidad(calidad)
        + _render_timeline(fases)
        + _render_archivos(payload, resultado.detalle_archivos, fases)
        + _render_muestra(datos_muestra)
        + _render_footer(job_id)
    )

    documento = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(titulo)}</title>
<style>{_CSS_TEMPLATE}</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
</head>
<body>
<div class="container">
{cuerpo}
</div>
</body>
</html>
"""
    ruta_salida.write_text(documento, encoding="utf-8")
    return ruta_salida
