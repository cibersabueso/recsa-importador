from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg import Connection

from db.db_config import DBConfig, cargar_config, resolver_db
from db.postgres_client import ensure_schema_para_pais, get_connection
from services._formato_tiempo import formatear_duracion

REPORTES_DIR: Path = Path(__file__).resolve().parent.parent / "reportes"
DASHBOARD_FILENAME: str = "dashboard.html"
DASHBOARD_VERSION: str = "0.3.0"

logger = logging.getLogger("recsa.dashboard")

ESTADOS_ORDEN: tuple[str, ...] = (
    "encolado",
    "procesando",
    "completado",
    "error",
    "fallido",
)

ESTADO_BADGE: dict[str, str] = {
    "encolado": "badge-blue",
    "procesando": "badge-yellow",
    "completado": "badge-green",
    "error": "badge-red",
    "fallido": "badge-gray",
}

ESTADO_ETIQUETA: dict[str, str] = {
    "encolado": "Encolados",
    "procesando": "Procesando",
    "completado": "Completados",
    "error": "Con error",
    "fallido": "Fallidos",
}


@dataclass
class EstadoStats:
    cantidad: int = 0
    total_filas: int = 0
    filas_validas: int = 0
    filas_con_error: int = 0
    sin_match: int = 0
    duracion_segundos: int = 0


@dataclass
class GrupoFila:
    pais: str
    grupo_prueba: str | None
    jobs: int
    total_filas: int
    total_validas: int
    total_errores: int
    total_sin_match: int
    duracion_promedio_seg: int
    primer_job: datetime | None
    ultimo_job: datetime | None


@dataclass
class JobReciente:
    pais: str
    job_id: str
    empresa: str | None
    grupo_prueba: str | None
    estado: str
    iniciado_en: datetime | None
    terminado_en: datetime | None
    total_filas: int
    filas_validas: int
    filas_con_error: int
    sin_match: int
    duracion_segundos: int | None


@dataclass
class PaisStats:
    pais: str
    db: str
    jobs: int = 0
    total_filas: int = 0
    filas_validas: int = 0
    duracion_segundos: int = 0


@dataclass
class DashboardData:
    paises: list[PaisStats] = field(default_factory=list)
    paises_con_error: list[tuple[str, str, str]] = field(default_factory=list)
    por_estado: dict[str, EstadoStats] = field(default_factory=dict)
    grupos: list[GrupoFila] = field(default_factory=list)
    recientes: list[JobReciente] = field(default_factory=list)
    generado_en: datetime = field(default_factory=datetime.now)


def _configs_paises() -> list[tuple[str, DBConfig]]:
    try:
        paises, default = cargar_config()
    except FileNotFoundError:
        return [("default", resolver_db(None))]
    items: list[tuple[str, DBConfig]] = [
        (codigo, cfg) for codigo, cfg in paises.items()
    ]
    items.append(("default", default))
    return items


def _consultar_estados(conn: Connection) -> dict[str, EstadoStats]:
    sql = """
        SELECT
            estado,
            COUNT(*) AS cantidad,
            COALESCE(SUM(total_filas), 0) AS total_filas,
            COALESCE(SUM(filas_validas), 0) AS filas_validas,
            COALESCE(SUM(filas_con_error), 0) AS filas_con_error,
            COALESCE(SUM(sin_match), 0) AS sin_match,
            COALESCE(SUM(duracion_segundos), 0) AS duracion_segundos
        FROM cargas_jobs
        GROUP BY estado
    """
    estados: dict[str, EstadoStats] = {}
    with conn.cursor() as cur:
        cur.execute(sql)
        for fila in cur.fetchall():
            estado = str(fila[0] or "")
            if not estado:
                continue
            estados[estado] = EstadoStats(
                cantidad=int(fila[1] or 0),
                total_filas=int(fila[2] or 0),
                filas_validas=int(fila[3] or 0),
                filas_con_error=int(fila[4] or 0),
                sin_match=int(fila[5] or 0),
                duracion_segundos=int(fila[6] or 0),
            )
    return estados


def _consultar_grupos(conn: Connection, pais: str) -> list[GrupoFila]:
    sql = """
        SELECT
            grupo_prueba,
            jobs,
            total_filas,
            total_validas,
            total_errores,
            total_sin_match,
            duracion_promedio_seg,
            primer_job,
            ultimo_job
        FROM vista_jobs_por_grupo
    """
    grupos: list[GrupoFila] = []
    with conn.cursor() as cur:
        cur.execute(sql)
        for fila in cur.fetchall():
            grupos.append(
                GrupoFila(
                    pais=pais,
                    grupo_prueba=fila[0],
                    jobs=int(fila[1] or 0),
                    total_filas=int(fila[2] or 0),
                    total_validas=int(fila[3] or 0),
                    total_errores=int(fila[4] or 0),
                    total_sin_match=int(fila[5] or 0),
                    duracion_promedio_seg=int(fila[6] or 0),
                    primer_job=fila[7],
                    ultimo_job=fila[8],
                )
            )
    return grupos


def _consultar_recientes(conn: Connection, pais: str, limite: int) -> list[JobReciente]:
    sql = """
        SELECT
            job_id,
            empresa,
            grupo_prueba,
            estado,
            iniciado_en,
            terminado_en,
            total_filas,
            filas_validas,
            filas_con_error,
            sin_match,
            duracion_segundos
        FROM cargas_jobs
        ORDER BY iniciado_en DESC
        LIMIT %s
    """
    recientes: list[JobReciente] = []
    with conn.cursor() as cur:
        cur.execute(sql, (limite,))
        for fila in cur.fetchall():
            recientes.append(
                JobReciente(
                    pais=pais,
                    job_id=str(fila[0]),
                    empresa=fila[1],
                    grupo_prueba=fila[2],
                    estado=str(fila[3] or ""),
                    iniciado_en=fila[4],
                    terminado_en=fila[5],
                    total_filas=int(fila[6] or 0),
                    filas_validas=int(fila[7] or 0),
                    filas_con_error=int(fila[8] or 0),
                    sin_match=int(fila[9] or 0),
                    duracion_segundos=int(fila[10]) if fila[10] is not None else None,
                )
            )
    return recientes


def _recolectar_pais(
    pais: str,
    cfg: DBConfig,
    data: DashboardData,
) -> None:
    pais_arg = None if pais == "default" else pais
    ensure_schema_para_pais(pais_arg)
    conn = get_connection(cfg)
    try:
        estados_pais = _consultar_estados(conn)
        grupos_pais = _consultar_grupos(conn, pais)
        recientes_pais = _consultar_recientes(conn, pais, 50)
    finally:
        conn.close()

    stats_pais = PaisStats(pais=pais, db=cfg.database)
    for estado, est in estados_pais.items():
        stats_pais.jobs += est.cantidad
        stats_pais.total_filas += est.total_filas
        stats_pais.filas_validas += est.filas_validas
        stats_pais.duracion_segundos += est.duracion_segundos
        agregado = data.por_estado.setdefault(estado, EstadoStats())
        agregado.cantidad += est.cantidad
        agregado.total_filas += est.total_filas
        agregado.filas_validas += est.filas_validas
        agregado.filas_con_error += est.filas_con_error
        agregado.sin_match += est.sin_match
        agregado.duracion_segundos += est.duracion_segundos

    data.paises.append(stats_pais)
    data.grupos.extend(grupos_pais)
    data.recientes.extend(recientes_pais)


def _recolectar_datos() -> DashboardData:
    data = DashboardData()
    for pais, cfg in _configs_paises():
        try:
            _recolectar_pais(pais, cfg, data)
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "Dashboard: BD '%s' (%s) no respondió: %s", pais, cfg.database, error
            )
            data.paises_con_error.append((pais, cfg.database, str(error)))
    data.grupos.sort(
        key=lambda g: g.ultimo_job or datetime.min,
        reverse=True,
    )
    data.recientes.sort(
        key=lambda j: j.iniciado_en or datetime.min,
        reverse=True,
    )
    data.recientes = data.recientes[:50]
    return data


def _esc(valor: Any) -> str:
    if valor is None:
        return ""
    return html.escape(str(valor), quote=True)


def _formato_dt(valor: datetime | None) -> str:
    if valor is None:
        return "-"
    return valor.strftime("%Y-%m-%d %H:%M:%S")


def _badge_estado(estado: str) -> str:
    clase = ESTADO_BADGE.get(estado, "badge-gray")
    return f'<span class="badge {clase}">{_esc(estado.upper())}</span>'


def _render_header(data: DashboardData) -> str:
    generado = data.generado_en.strftime("%Y-%m-%d %H:%M:%S")
    paises_count = len(data.paises)
    return f"""
<header>
  <div class="header-top">
    <div>
      <h1>Dashboard RECSA Cargas</h1>
      <div class="subtitulo">Vista global de procesamientos por país y grupo</div>
    </div>
    <div class="header-actions">
      <span class="badge badge-blue">Generado: {_esc(generado)}</span>
      <a class="boton" href="/api/dashboard">Refrescar</a>
    </div>
  </div>
  <div class="meta">
    <div><strong>Países consultados:</strong> {paises_count}</div>
    <div><strong>BDs con error:</strong> {len(data.paises_con_error)}</div>
    <div><strong>Versión motor:</strong> v{DASHBOARD_VERSION}</div>
  </div>
</header>
"""


def _render_warnings(data: DashboardData) -> str:
    if not data.paises_con_error:
        return ""
    items: list[str] = []
    for pais, db, error in data.paises_con_error:
        items.append(
            f"<li><strong>{_esc(pais)}</strong> "
            f"(<code>{_esc(db)}</code>): {_esc(error)}</li>"
        )
    return f"""
<section class="warning">
  <h2>Advertencias</h2>
  <p class="muted">
    No se pudo consultar las siguientes BDs. Los datos del dashboard son
    parciales (excluyen estos países).
  </p>
  <ul>{''.join(items)}</ul>
</section>
"""


def _render_kpis(data: DashboardData) -> str:
    total_jobs = sum(p.jobs for p in data.paises)
    total_filas = sum(p.total_filas for p in data.paises)
    total_validas = sum(p.filas_validas for p in data.paises)
    total_duracion = sum(p.duracion_segundos for p in data.paises)
    return f"""
<section>
  <h2>KPIs globales</h2>
  <div class="cards cards-4 cards-xl">
    <div class="card">
      <div class="label">Jobs ejecutados</div>
      <div class="value">{total_jobs:,}</div>
    </div>
    <div class="card">
      <div class="label">Filas procesadas</div>
      <div class="value">{total_filas:,}</div>
    </div>
    <div class="card green">
      <div class="label">Filas válidas (persistidas)</div>
      <div class="value">{total_validas:,}</div>
    </div>
    <div class="card blue">
      <div class="label">Tiempo total acumulado</div>
      <div class="value">{_esc(formatear_duracion(total_duracion))}</div>
    </div>
  </div>
</section>
"""


def _render_estados(data: DashboardData) -> str:
    cards: list[str] = []
    for estado in ESTADOS_ORDEN:
        if estado == "fallido":
            continue
        stats = data.por_estado.get(estado, EstadoStats())
        clase_estado = ESTADO_BADGE.get(estado, "badge-gray").replace("badge-", "")
        cards.append(
            f"""
    <div class="card mini estado-{clase_estado}">
      <div class="label">{_esc(ESTADO_ETIQUETA.get(estado, estado))}</div>
      <div class="value">{stats.cantidad:,}</div>
    </div>
"""
        )
    return f"""
<section>
  <h2>Estado de jobs</h2>
  <div class="cards cards-4">
    {''.join(cards)}
  </div>
</section>
"""


def _render_distribucion(data: DashboardData) -> str:
    if not data.paises:
        return ""
    paises_ordenados = sorted(
        data.paises, key=lambda p: p.filas_validas, reverse=True
    )
    chart_data = {
        "labels": [p.pais for p in paises_ordenados],
        "filas_validas": [p.filas_validas for p in paises_ordenados],
        "jobs": [p.jobs for p in paises_ordenados],
    }
    data_json = json.dumps(chart_data, ensure_ascii=False)
    return f"""
<section>
  <h2>Distribución por país</h2>
  <p class="muted">
    Filas válidas (persistidas en cada BD) y cantidad de jobs por país.
  </p>
  <div class="chart-container">
    <canvas id="paisChart"></canvas>
  </div>
  <script>
    (function() {{
      const data = {data_json};
      const ctx = document.getElementById('paisChart');
      new Chart(ctx, {{
        type: 'bar',
        data: {{
          labels: data.labels,
          datasets: [
            {{
              label: 'Filas válidas',
              data: data.filas_validas,
              backgroundColor: '#1e3a8a',
              borderRadius: 4,
              yAxisID: 'y'
            }},
            {{
              label: 'Jobs',
              data: data.jobs,
              backgroundColor: '#f59e0b',
              borderRadius: 4,
              yAxisID: 'y1'
            }}
          ]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ position: 'bottom' }}
          }},
          scales: {{
            y: {{
              type: 'linear',
              position: 'left',
              beginAtZero: true,
              title: {{ display: true, text: 'Filas' }},
              ticks: {{
                callback: function(value) {{
                  return value.toLocaleString();
                }}
              }}
            }},
            y1: {{
              type: 'linear',
              position: 'right',
              beginAtZero: true,
              title: {{ display: true, text: 'Jobs' }},
              grid: {{ drawOnChartArea: false }}
            }}
          }}
        }}
      }});
    }})();
  </script>
</section>
"""


def _render_grupos(data: DashboardData) -> str:
    if not data.grupos:
        return f"""
<section>
  <h2>Grupos de prueba</h2>
  <p class="muted">No hay jobs completados con grupo de prueba registrado.</p>
</section>
"""
    filas: list[str] = []
    for grupo in data.grupos:
        nombre_grupo = grupo.grupo_prueba or "(sin grupo)"
        filas.append(
            f"""
      <tr>
        <td>{_esc(nombre_grupo)}</td>
        <td>{_esc(grupo.pais)}</td>
        <td class="num">{grupo.jobs:,}</td>
        <td class="num">{grupo.total_filas:,}</td>
        <td class="num">{grupo.total_validas:,}</td>
        <td class="num">{grupo.total_errores:,}</td>
        <td class="num">{grupo.total_sin_match:,}</td>
        <td class="num">{_esc(formatear_duracion(grupo.duracion_promedio_seg))}</td>
        <td>{_esc(_formato_dt(grupo.ultimo_job))}</td>
      </tr>
"""
        )
    return f"""
<section>
  <h2>Grupos de prueba</h2>
  <p class="muted">
    Comparativa entre grupos de prueba (basada en
    <code>vista_jobs_por_grupo</code>: jobs completados).
  </p>
  <div class="tabla-scroll">
    <table>
      <thead>
        <tr>
          <th>Grupo</th>
          <th>País</th>
          <th class="num">Jobs</th>
          <th class="num">Total filas</th>
          <th class="num">Total válidas</th>
          <th class="num">Total errores</th>
          <th class="num">Total sin match</th>
          <th class="num">Duración promedio</th>
          <th>Último job</th>
        </tr>
      </thead>
      <tbody>
        {''.join(filas)}
      </tbody>
    </table>
  </div>
</section>
"""


def _render_progreso_celda(job: JobReciente) -> str:
    if job.estado != "procesando":
        return '<span class="muted">-</span>'
    return (
        f'<div class="progreso-bar" data-job-progress="{_esc(job.job_id)}" '
        f'title="Esperando datos...">'
        f'<div class="progreso-fill" style="width: 0%"></div>'
        f'<span class="progreso-label">Iniciando...</span>'
        f"</div>"
    )


def _render_recientes(data: DashboardData) -> str:
    if not data.recientes:
        return f"""
<section>
  <h2>Jobs recientes</h2>
  <p class="muted">No hay jobs registrados todavía.</p>
</section>
"""
    filas: list[str] = []
    for job in data.recientes:
        empresa = job.empresa or "-"
        grupo = job.grupo_prueba or "-"
        acciones = (
            f'<a class="link" href="/api/jobs/{_esc(job.job_id)}">Detalle</a> '
            f'<a class="link" href="/api/jobs/{_esc(job.job_id)}/log">Log</a> '
            f'<a class="link" href="/api/jobs/{_esc(job.job_id)}/report">HTML</a>'
        )
        filas.append(
            f"""
      <tr>
        <td>{_esc(_formato_dt(job.iniciado_en))}</td>
        <td>{_esc(job.pais)}</td>
        <td>{_esc(empresa)}</td>
        <td>{_esc(grupo)}</td>
        <td>{_badge_estado(job.estado)}</td>
        <td class="progreso-celda">{_render_progreso_celda(job)}</td>
        <td class="num">{job.total_filas:,}</td>
        <td class="num">{job.filas_validas:,}</td>
        <td class="num">{job.sin_match:,}</td>
        <td class="num">{_esc(formatear_duracion(job.duracion_segundos))}</td>
        <td class="acciones">{acciones}</td>
      </tr>
"""
        )
    return f"""
<section>
  <h2>Jobs recientes</h2>
  <p class="muted">
    Últimas {len(data.recientes)} corridas mezcladas de todos los países,
    ordenadas por fecha de inicio descendente. Los jobs en estado
    <em>procesando</em> muestran progreso en vivo (refresco cada 2s).
  </p>
  <div class="tabla-scroll">
    <table class="recientes">
      <thead>
        <tr>
          <th>Fecha / hora</th>
          <th>País</th>
          <th>Empresa</th>
          <th>Grupo</th>
          <th>Estado</th>
          <th>Progreso</th>
          <th class="num">Leídas</th>
          <th class="num">Válidas</th>
          <th class="num">Sin match</th>
          <th class="num">Duración</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        {''.join(filas)}
      </tbody>
    </table>
  </div>
</section>
"""


def _render_footer(data: DashboardData) -> str:
    generado = data.generado_en.strftime("%Y-%m-%d %H:%M:%S")
    return f"""
<footer>
  <div>Generado por motor RECSA Cargas v{DASHBOARD_VERSION}</div>
  <div>Generado el: {_esc(generado)}</div>
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
.container { max-width: 1400px; margin: 0 auto; }
header {
  background: #ffffff;
  padding: 1.75rem 2rem;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  margin-bottom: 1.5rem;
  border-left: 6px solid #1e3a8a;
}
.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 0.75rem;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
header h1 { color: #1e3a8a; font-size: 1.75rem; margin-bottom: 0.5rem; }
header .subtitulo { color: #4b5563; font-size: 0.95rem; }
header .meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.5rem 1.5rem;
  color: #4b5563;
  font-size: 0.9rem;
  margin-top: 0.5rem;
}
header .meta strong { color: #1f2937; font-weight: 600; }
code { font-family: "SFMono-Regular", Consolas, Menlo, monospace; font-size: 0.85em; background: #f3f4f6; padding: 0.1rem 0.35rem; border-radius: 4px; }
.boton {
  display: inline-block;
  padding: 0.45rem 1rem;
  background: #1e3a8a;
  color: #ffffff;
  text-decoration: none;
  border-radius: 0.4rem;
  font-weight: 600;
  font-size: 0.85rem;
  letter-spacing: 0.04em;
  transition: background 0.15s ease;
}
.boton:hover { background: #1e40af; }
.badge {
  display: inline-block;
  padding: 0.28rem 0.75rem;
  border-radius: 9999px;
  font-weight: 600;
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.badge-blue { background: #dbeafe; color: #1d4ed8; }
.badge-yellow { background: #fef3c7; color: #b45309; }
.badge-green { background: #dcfce7; color: #16a34a; }
.badge-red { background: #fee2e2; color: #dc2626; }
.badge-gray { background: #e5e7eb; color: #4b5563; }
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
section.warning {
  border-left: 4px solid #f59e0b;
  background: #fffbeb;
}
section.warning h2 { color: #92400e; }
section.warning ul { padding-left: 1.5rem; color: #92400e; }
.muted { color: #6b7280; font-size: 0.875rem; margin-bottom: 0.75rem; }
.cards { display: grid; gap: 1rem; }
.cards-4 { grid-template-columns: repeat(4, 1fr); }
.card {
  background: #f9fafb;
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  text-align: left;
  border-left: 4px solid #d1d5db;
}
.card.green { border-color: #16a34a; }
.card.blue { border-color: #1e3a8a; }
.card.yellow { border-color: #f59e0b; }
.card.red { border-color: #dc2626; }
.card.mini { padding: 0.85rem 1rem; }
.card.mini .value { font-size: 1.5rem; }
.card.estado-blue { border-color: #1d4ed8; }
.card.estado-yellow { border-color: #b45309; }
.card.estado-green { border-color: #16a34a; }
.card.estado-red { border-color: #dc2626; }
.card.estado-gray { border-color: #6b7280; }
.cards-xl .card { padding: 1.25rem 1.5rem; }
.cards-xl .value { font-size: 2rem; }
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
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
th, td {
  text-align: left;
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid #e5e7eb;
}
th {
  background: #f3f4f6;
  font-weight: 600;
  color: #374151;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
th.num, td.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr:nth-child(even) { background: #f9fafb; }
tbody tr:hover { background: #eff6ff; }
.tabla-scroll { overflow-x: auto; }
.acciones { white-space: nowrap; }
.link {
  color: #1e3a8a;
  text-decoration: none;
  font-weight: 500;
  margin-right: 0.4rem;
}
.link:hover { text-decoration: underline; }
.recientes td { font-size: 0.85rem; }
.progreso-celda { min-width: 220px; }
.progreso-bar {
  position: relative;
  width: 220px;
  height: 1.45rem;
  background: #e5e7eb;
  border-radius: 0.3rem;
  overflow: hidden;
  border: 1px solid #d1d5db;
}
.progreso-fill {
  height: 100%;
  width: 0%;
  background-color: #1e3a8a;
  background-image: linear-gradient(
    45deg,
    rgba(255,255,255,0.18) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255,255,255,0.18) 50%,
    rgba(255,255,255,0.18) 75%,
    transparent 75%
  );
  background-size: 18px 18px;
  animation: progreso-stripes 1.2s linear infinite;
  transition: width 0.4s ease-out;
}
.progreso-label {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 600;
  color: #ffffff;
  text-shadow: 0 0 3px rgba(0,0,0,0.55);
  letter-spacing: 0.02em;
  white-space: nowrap;
  padding: 0 0.4rem;
}
@keyframes progreso-stripes {
  from { background-position: 0 0; }
  to { background-position: 18px 0; }
}
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
@media (max-width: 1100px) {
  .cards-4 { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .cards-4 { grid-template-columns: 1fr; }
  body { padding: 1rem 0.5rem; }
  header { padding: 1.25rem; }
  section { padding: 1.1rem; }
}
"""


_PROGRESO_SCRIPT: str = """
(function() {
  const POLL_MS = 2000;

  function fmt(n) {
    if (n === null || n === undefined) return '-';
    return Number(n).toLocaleString('es-CL');
  }

  function refrescar(container) {
    const jobId = container.getAttribute('data-job-progress');
    if (!jobId) return Promise.resolve();
    return fetch('/api/jobs/' + encodeURIComponent(jobId) + '/progreso', {
      headers: { 'Accept': 'application/json' },
      cache: 'no-store'
    })
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (!data) return;
        const fill = container.querySelector('.progreso-fill');
        const label = container.querySelector('.progreso-label');
        if (data.estado !== 'procesando') {
          container.removeAttribute('data-job-progress');
          if (fill) fill.style.width = '100%';
          if (label) label.textContent = String(data.estado || '').toUpperCase();
          container.title = 'Estado final: ' + (data.estado || '?');
          return;
        }
        const pct = Math.max(0, Math.min(100, Number(data.porcentaje_fase || 0)));
        const idx = Number(data.fase_indice || 0);
        const total = Number(data.fase_total || 0);
        if (fill) fill.style.width = pct.toFixed(1) + '%';
        if (label) {
          const fase = total > 0 ? ('Fase ' + idx + '/' + total) : ('Fase ' + idx);
          label.textContent = fase + ': ' + pct.toFixed(1) + '%';
        }
        container.title =
          (data.fase_actual || '') +
          '\\n' + fmt(data.filas_procesadas) + ' / ' + fmt(data.filas_totales) + ' filas' +
          '\\nVelocidad: ' + fmt(data.velocidad_filas_seg) + ' filas/s' +
          '\\nTranscurrido: ' + fmt(data.tiempo_transcurrido_seg) + 's' +
          (data.tiempo_estimado_restante_seg !== null && data.tiempo_estimado_restante_seg !== undefined
            ? '\\nRestante (estim.): ' + fmt(data.tiempo_estimado_restante_seg) + 's'
            : '');
      })
      .catch(function(err) {
        console.warn('progreso job', jobId, err);
      });
  }

  function tick() {
    const containers = document.querySelectorAll('[data-job-progress]');
    if (containers.length === 0) return;
    containers.forEach(refrescar);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick);
  } else {
    tick();
  }
  setInterval(tick, POLL_MS);
})();
"""


def generar_dashboard(ruta_salida: Path | None = None) -> Path:
    if ruta_salida is None:
        ruta_salida = REPORTES_DIR / DASHBOARD_FILENAME
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    data = _recolectar_datos()

    cuerpo = (
        _render_header(data)
        + _render_warnings(data)
        + _render_kpis(data)
        + _render_estados(data)
        + _render_distribucion(data)
        + _render_grupos(data)
        + _render_recientes(data)
        + _render_footer(data)
    )

    titulo = "Dashboard RECSA Cargas"
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
<script>{_PROGRESO_SCRIPT}</script>
</body>
</html>
"""
    ruta_salida.write_text(documento, encoding="utf-8")
    return ruta_salida
