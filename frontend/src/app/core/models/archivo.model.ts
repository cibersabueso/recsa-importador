export type TipoArchivo = 'csv' | 'txt' | 'xlsx' | 'xml' | 'json';

export type EstadoArchivo = 'pendiente' | 'configurado';

export interface ArchivoSubido {
  id: string;
  nombre: string;
  tamanio: number;
  tipo: TipoArchivo;
  orden: number;
  estado: EstadoArchivo;
  delimitador: Delimitador;
  separadorDecimal: SeparadorDecimal;
  codificacion: Codificacion;
  tieneEncabezados: boolean;
  columnas: string[];
  previsualizacion: string[][];
  columnaClave: string | null;
  columnaJoin: string | null;
  archivoIdServidor?: string;
  rutaServidor?: string;
}

export interface UploadArchivoRespuesta {
  archivoId: string;
  nombre: string;
  tipo: TipoArchivo;
  tamano: number;
  ruta: string;
  codificacionDetectada: string | null;
  delimitadorDetectado: string | null;
}

export interface UploadRespuesta {
  archivos: UploadArchivoRespuesta[];
}

export type Delimitador = ';' | ',' | '|' | '\t';

export type SeparadorDecimal = ',' | '.';

export type Codificacion = 'UTF-8' | 'Latin1' | 'Windows-1252';

export const FORMATOS_ACEPTADOS: readonly string[] = [
  '.csv',
  '.txt',
  '.xlsx',
  '.xml',
  '.json',
] as const;

export function detectarTipoArchivo(nombre: string): TipoArchivo {
  const ext = nombre.toLowerCase().split('.').pop() ?? '';
  if (ext === 'csv') return 'csv';
  if (ext === 'txt') return 'txt';
  if (ext === 'xlsx' || ext === 'xls') return 'xlsx';
  if (ext === 'xml') return 'xml';
  if (ext === 'json') return 'json';
  return 'txt';
}

export function formatearTamanio(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
