export interface ResultadoArchivo {
  archivoId: string;
  nombre: string;
  filasValidas: number;
  filasConError: number;
  duplicados: number;
}

export interface ResultadoImportacion {
  jobId: string;
  estado: 'pendiente' | 'en_proceso' | 'completado' | 'error';
  filasValidas: number;
  filasConError: number;
  duplicados: number;
  archivos: ResultadoArchivo[];
}
