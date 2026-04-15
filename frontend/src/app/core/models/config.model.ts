export interface ConfiguracionProceso {
  empresa: string;
  tipoCarga: string;
  tipoProceso: string;
  nombreInterfaz: string;
  responsable: string;
}

export const PROCESO_VACIO: ConfiguracionProceso = {
  empresa: '',
  tipoCarga: '',
  tipoProceso: '',
  nombreInterfaz: '',
  responsable: '',
};

export interface OpcionSelect {
  valor: string;
  etiqueta: string;
}

export const OPCIONES_EMPRESA: readonly OpcionSelect[] = [
  { valor: 'PE_BBVA', etiqueta: 'PE — BBVA' },
  { valor: 'PE_INTERBANK', etiqueta: 'PE — Interbank' },
  { valor: 'CL_BANCOESTADO', etiqueta: 'CL — BancoEstado' },
  { valor: 'CO_BANCOLOMBIA', etiqueta: 'CO — Bancolombia' },
  { valor: 'MX_BBVA', etiqueta: 'MX — BBVA' },
];

export const OPCIONES_TIPO_CARGA: readonly OpcionSelect[] = [
  { valor: 'asignacion', etiqueta: 'Asignación' },
  { valor: 'actualizacion', etiqueta: 'Actualización' },
  { valor: 'pagos', etiqueta: 'Pagos' },
  { valor: 'retiro', etiqueta: 'Retiro de cartera' },
];

export const OPCIONES_TIPO_PROCESO: readonly OpcionSelect[] = [
  { valor: 'inicial', etiqueta: 'Inicial' },
  { valor: 'incremental', etiqueta: 'Incremental' },
  { valor: 'correccion', etiqueta: 'Corrección' },
];

export const OPCIONES_NOMBRE_INTERFAZ: readonly OpcionSelect[] = [
  { valor: 'IF_BBVA_001', etiqueta: 'IF_BBVA_001' },
  { valor: 'IF_BBVA_002', etiqueta: 'IF_BBVA_002' },
  { valor: 'IF_INTER_001', etiqueta: 'IF_INTER_001' },
  { valor: 'IF_BANEST_001', etiqueta: 'IF_BANEST_001' },
  { valor: 'IF_BCOL_001', etiqueta: 'IF_BCOL_001' },
];

export const OPCIONES_DELIMITADOR: readonly { valor: string; etiqueta: string }[] = [
  { valor: ';', etiqueta: 'Punto y coma (;)' },
  { valor: ',', etiqueta: 'Coma (,)' },
  { valor: '|', etiqueta: 'Barra vertical (|)' },
  { valor: '\t', etiqueta: 'Tabulación' },
];

export const OPCIONES_SEPARADOR_DECIMAL: readonly { valor: string; etiqueta: string }[] = [
  { valor: ',', etiqueta: 'Coma (,)' },
  { valor: '.', etiqueta: 'Punto (.)' },
];

export const OPCIONES_CODIFICACION: readonly { valor: string; etiqueta: string }[] = [
  { valor: 'UTF-8', etiqueta: 'UTF-8' },
  { valor: 'Latin1', etiqueta: 'Latin1' },
  { valor: 'Windows-1252', etiqueta: 'Windows-1252' },
];
