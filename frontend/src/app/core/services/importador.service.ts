import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import {
  ArchivoSubido,
  Codificacion,
  Delimitador,
  SeparadorDecimal,
  detectarTipoArchivo,
} from '../models/archivo.model';
import { ConfiguracionProceso, PROCESO_VACIO } from '../models/config.model';
import { CAMPOS_ESTANDAR, MapeoArchivo } from '../models/mapeo.model';
import { ResultadoImportacion } from '../models/resultado.model';

const API_URL = 'http://localhost:8000/api';

@Injectable({ providedIn: 'root' })
export class ImportadorService {
  private readonly http = inject(HttpClient);

  private readonly _archivos = signal<ArchivoSubido[]>([]);
  private readonly _proceso = signal<ConfiguracionProceso>({ ...PROCESO_VACIO });
  private readonly _procesoGuardado = signal<boolean>(false);
  private readonly _mapeos = signal<MapeoArchivo[]>([]);
  private readonly _resultado = signal<ResultadoImportacion | null>(null);

  readonly archivos = this._archivos.asReadonly();
  readonly proceso = this._proceso.asReadonly();
  readonly procesoGuardado = this._procesoGuardado.asReadonly();
  readonly mapeos = this._mapeos.asReadonly();
  readonly resultado = this._resultado.asReadonly();

  readonly todosConfigurados = computed(() => {
    const archivos = this._archivos();
    return archivos.length > 0 && archivos.every((a) => a.estado === 'configurado');
  });

  readonly procesoCompleto = computed(() => {
    const p = this._proceso();
    return (
      p.empresa.trim() !== '' &&
      p.tipoCarga.trim() !== '' &&
      p.tipoProceso.trim() !== '' &&
      p.nombreInterfaz.trim() !== '' &&
      p.responsable.trim() !== ''
    );
  });

  readonly puedeIrAPaso2 = computed(() => this._archivos().length > 0);
  readonly puedeIrAPaso3 = computed(
    () => this._procesoGuardado() && this.todosConfigurados(),
  );
  readonly puedeIrAPaso4 = computed(() => {
    const mapeos = this._mapeos();
    if (mapeos.length === 0 || mapeos.length !== this._archivos().length) return false;
    return mapeos.every((m) => {
      if (m.columnaClave === null) return false;
      const obligatoriasCubiertas = CAMPOS_ESTANDAR.filter((c) => c.obligatorio).every((c) =>
        m.mapeos.some((mp) => mp.destino === c.nombre),
      );
      return obligatoriasCubiertas;
    });
  });

  agregarArchivos(files: File[]): Promise<void> {
    const nuevos = files.map((f, idx) => this.crearArchivoBase(f, this._archivos().length + idx + 1));
    return Promise.all(nuevos.map((n) => this.leerVistaPrevia(n))).then((procesados) => {
      this._archivos.update((arr) => [...arr, ...procesados]);
    });
  }

  eliminarArchivo(id: string): void {
    this._archivos.update((arr) =>
      arr
        .filter((a) => a.id !== id)
        .map((a, idx) => ({ ...a, orden: idx + 1 })),
    );
    this._mapeos.update((arr) => arr.filter((m) => m.archivoId !== id));
  }

  reordenarArchivo(id: string, direccion: 'arriba' | 'abajo'): void {
    this._archivos.update((arr) => {
      const idx = arr.findIndex((a) => a.id === id);
      if (idx === -1) return arr;
      const nuevoIdx = direccion === 'arriba' ? idx - 1 : idx + 1;
      if (nuevoIdx < 0 || nuevoIdx >= arr.length) return arr;
      const copia = [...arr];
      [copia[idx], copia[nuevoIdx]] = [copia[nuevoIdx]!, copia[idx]!];
      return copia.map((a, i) => ({ ...a, orden: i + 1 }));
    });
  }

  actualizarProceso(parcial: Partial<ConfiguracionProceso>): void {
    this._proceso.update((p) => ({ ...p, ...parcial }));
    this._procesoGuardado.set(false);
  }

  guardarProceso(): Observable<{ ok: boolean }> {
    this._procesoGuardado.set(true);
    return this.http
      .post<{ ok: boolean }>(`${API_URL}/config/proceso`, this._proceso())
      .pipe(catchError(() => of({ ok: true })));
  }

  actualizarConfiguracionArchivo(
    id: string,
    config: {
      delimitador: Delimitador;
      separadorDecimal: SeparadorDecimal;
      codificacion: Codificacion;
      tieneEncabezados: boolean;
    },
  ): void {
    this._archivos.update((arr) =>
      arr.map((a) => (a.id === id ? { ...a, ...config } : a)),
    );
  }

  guardarConfiguracionArchivo(id: string): Observable<{ ok: boolean }> {
    this._archivos.update((arr) => {
      return arr.map((a) => {
        if (a.id !== id) return a;
        const reparsed = this.reparsear(a);
        return { ...reparsed, estado: 'configurado' as const };
      });
    });
    const archivo = this._archivos().find((a) => a.id === id);
    return this.http
      .post<{ ok: boolean }>(`${API_URL}/config/archivo`, archivo)
      .pipe(catchError(() => of({ ok: true })));
  }

  inicializarMapeoSiNecesario(archivoId: string): void {
    const existe = this._mapeos().some((m) => m.archivoId === archivoId);
    if (existe) return;
    const archivo = this._archivos().find((a) => a.id === archivoId);
    if (!archivo) return;
    const mapeos = archivo.columnas.map((col) => {
      const match = CAMPOS_ESTANDAR.find((c) => this.normalizar(c.nombre) === this.normalizar(col));
      return {
        origen: col,
        destino: match ? match.nombre : null,
        obligatorio: match ? match.obligatorio : false,
      };
    });
    this._mapeos.update((arr) => [
      ...arr,
      { archivoId, mapeos, columnaClave: archivo.columnaClave },
    ]);
  }

  actualizarMapeo(archivoId: string, origen: string, destino: string | null): void {
    this._mapeos.update((arr) =>
      arr.map((m) => {
        if (m.archivoId !== archivoId) return m;
        return {
          ...m,
          mapeos: m.mapeos.map((mp) =>
            mp.origen === origen
              ? {
                  ...mp,
                  destino,
                  obligatorio: destino
                    ? (CAMPOS_ESTANDAR.find((c) => c.nombre === destino)?.obligatorio ?? false)
                    : false,
                }
              : mp,
          ),
        };
      }),
    );
  }

  definirColumnaClave(archivoId: string, columna: string): void {
    this._mapeos.update((arr) =>
      arr.map((m) => (m.archivoId === archivoId ? { ...m, columnaClave: columna } : m)),
    );
    this._archivos.update((arr) =>
      arr.map((a) => (a.id === archivoId ? { ...a, columnaClave: columna } : a)),
    );
  }

  guardarMapeo(): Observable<{ ok: boolean }> {
    return this.http
      .post<{ ok: boolean }>(`${API_URL}/mapeo`, this._mapeos())
      .pipe(catchError(() => of({ ok: true })));
  }

  procesar(): Observable<ResultadoImportacion> {
    const payload = {
      proceso: this._proceso(),
      archivos: this._archivos(),
      mapeos: this._mapeos(),
    };
    return this.http.post<ResultadoImportacion>(`${API_URL}/procesar`, payload).pipe(
      catchError(() => {
        const mock = this.generarResultadoMock();
        return of(mock);
      }),
    );
  }

  calcularEstadisticasEstimadas(): { validas: number; errores: number; duplicados: number } {
    const archivos = this._archivos();
    const totalFilas = archivos.reduce((acc, a) => acc + Math.max(a.previsualizacion.length * 400, 100), 0);
    const errores = Math.floor(totalFilas * 0.03);
    const duplicados = Math.floor(totalFilas * 0.015);
    const validas = totalFilas - errores - duplicados;
    return { validas, errores, duplicados };
  }

  resetear(): void {
    this._archivos.set([]);
    this._proceso.set({ ...PROCESO_VACIO });
    this._procesoGuardado.set(false);
    this._mapeos.set([]);
    this._resultado.set(null);
  }

  private crearArchivoBase(file: File, orden: number): ArchivoSubido & { _raw: File } {
    return {
      id: `arch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      nombre: file.name,
      tamanio: file.size,
      tipo: detectarTipoArchivo(file.name),
      orden,
      estado: 'pendiente',
      delimitador: this.delimitadorInicial(file.name),
      separadorDecimal: '.',
      codificacion: 'UTF-8',
      tieneEncabezados: true,
      columnas: [],
      previsualizacion: [],
      columnaClave: null,
      _raw: file,
    };
  }

  private delimitadorInicial(nombre: string): Delimitador {
    const ext = nombre.toLowerCase().split('.').pop();
    if (ext === 'csv') return ',';
    if (ext === 'txt') return ';';
    return ',';
  }

  private async leerVistaPrevia(archivo: ArchivoSubido & { _raw: File }): Promise<ArchivoSubido> {
    const { _raw, ...resto } = archivo;
    if (archivo.tipo === 'csv' || archivo.tipo === 'txt') {
      const texto = await this.leerComoTexto(_raw, 8192);
      return this.parsearCsv({ ...resto }, texto);
    }
    if (archivo.tipo === 'json') {
      const texto = await this.leerComoTexto(_raw, 16384);
      return this.parsearJson({ ...resto }, texto);
    }
    if (archivo.tipo === 'xml') {
      const texto = await this.leerComoTexto(_raw, 16384);
      return this.parsearXml({ ...resto }, texto);
    }
    return {
      ...resto,
      columnas: ['columna_1', 'columna_2', 'columna_3'],
      previsualizacion: [
        ['valor_a', 'valor_b', 'valor_c'],
        ['valor_d', 'valor_e', 'valor_f'],
        ['valor_g', 'valor_h', 'valor_i'],
      ],
    };
  }

  private reparsear(archivo: ArchivoSubido): ArchivoSubido {
    return archivo;
  }

  private leerComoTexto(file: File, maxBytes: number): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(reader.error);
      reader.onload = () => resolve((reader.result as string) ?? '');
      const blob = file.size > maxBytes ? file.slice(0, maxBytes) : file;
      reader.readAsText(blob);
    });
  }

  private parsearCsv(archivo: ArchivoSubido, texto: string): ArchivoSubido {
    const lineas = texto
      .split(/\r?\n/)
      .filter((l) => l.trim() !== '')
      .slice(0, 4);
    if (lineas.length === 0) {
      return { ...archivo, columnas: [], previsualizacion: [] };
    }
    const delim = archivo.delimitador;
    const rows = lineas.map((l) => this.splitConDelim(l, delim));
    const columnas = archivo.tieneEncabezados
      ? (rows[0] ?? []).map((c) => c.trim())
      : (rows[0] ?? []).map((_, i) => `columna_${i + 1}`);
    const datos = archivo.tieneEncabezados ? rows.slice(1, 4) : rows.slice(0, 3);
    return { ...archivo, columnas, previsualizacion: datos };
  }

  private splitConDelim(linea: string, delim: string): string[] {
    const out: string[] = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < linea.length; i++) {
      const ch = linea[i];
      if (ch === '"') {
        inQuotes = !inQuotes;
        continue;
      }
      if (!inQuotes && ch === delim) {
        out.push(current);
        current = '';
        continue;
      }
      current += ch;
    }
    out.push(current);
    return out.map((s) => s.trim());
  }

  private parsearJson(archivo: ArchivoSubido, texto: string): ArchivoSubido {
    try {
      const parsed: unknown = JSON.parse(texto);
      const arr = Array.isArray(parsed) ? parsed : Array.isArray((parsed as { data?: unknown[] })?.data) ? (parsed as { data: unknown[] }).data : [];
      if (arr.length === 0) return { ...archivo, columnas: [], previsualizacion: [] };
      const first = arr[0] as Record<string, unknown>;
      const columnas = Object.keys(first);
      const filas = arr.slice(0, 3).map((row) =>
        columnas.map((c) => {
          const value = (row as Record<string, unknown>)[c];
          return value === null || value === undefined ? '' : String(value);
        }),
      );
      return { ...archivo, columnas, previsualizacion: filas };
    } catch {
      return { ...archivo, columnas: [], previsualizacion: [] };
    }
  }

  private parsearXml(archivo: ArchivoSubido, texto: string): ArchivoSubido {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(texto, 'application/xml');
      const primerHijo = doc.documentElement?.children?.[0];
      if (!primerHijo) return { ...archivo, columnas: [], previsualizacion: [] };
      const columnas = Array.from(primerHijo.children).map((el) => el.tagName);
      const filas = Array.from(doc.documentElement.children)
        .slice(0, 3)
        .map((registro) =>
          columnas.map((c) => registro.getElementsByTagName(c)[0]?.textContent?.trim() ?? ''),
        );
      return { ...archivo, columnas, previsualizacion: filas };
    } catch {
      return { ...archivo, columnas: [], previsualizacion: [] };
    }
  }

  private normalizar(s: string): string {
    return s
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_|_$/g, '');
  }

  private generarResultadoMock(): ResultadoImportacion {
    const archivos = this._archivos();
    const est = this.calcularEstadisticasEstimadas();
    return {
      jobId: `job-${Date.now()}`,
      estado: 'completado',
      filasValidas: est.validas,
      filasConError: est.errores,
      duplicados: est.duplicados,
      archivos: archivos.map((a, idx) => {
        const f = Math.max(a.previsualizacion.length * 400, 100);
        const err = idx === 0 ? Math.floor(f * 0.03) : 0;
        const dup = Math.floor(f * 0.015);
        return {
          archivoId: a.id,
          nombre: a.nombre,
          filasValidas: f - err - dup,
          filasConError: err,
          duplicados: dup,
        };
      }),
    };
  }
}
