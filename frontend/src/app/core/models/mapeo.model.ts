export interface CampoEstandar {
  nombre: string;
  etiqueta: string;
  obligatorio: boolean;
}

export interface Mapeo {
  origen: string;
  destino: string | null;
  obligatorio: boolean;
}

export interface MapeoArchivo {
  archivoId: string;
  mapeos: Mapeo[];
  columnaClave: string | null;
  columnaJoin: string | null;
}

export const CAMPOS_ESTANDAR: readonly CampoEstandar[] = [
  { nombre: 'root_cliente', etiqueta: 'Root cliente', obligatorio: true },
  { nombre: 'nombre_completo', etiqueta: 'Nombre completo', obligatorio: true },
  { nombre: 'direccion', etiqueta: 'Dirección', obligatorio: true },
  { nombre: 'telefono_principal', etiqueta: 'Teléfono principal', obligatorio: true },
  { nombre: 'telefono_secundario', etiqueta: 'Teléfono secundario', obligatorio: true },
  { nombre: 'email', etiqueta: 'Email', obligatorio: true },
  { nombre: 'monto_deuda_original', etiqueta: 'Monto deuda original', obligatorio: true },
  { nombre: 'monto_deuda_actual', etiqueta: 'Monto deuda actual', obligatorio: true },
  { nombre: 'fecha_vencimiento', etiqueta: 'Fecha de vencimiento', obligatorio: true },
  { nombre: 'numero_documento', etiqueta: 'Número de documento', obligatorio: true },
  { nombre: 'producto', etiqueta: 'Producto', obligatorio: true },
  { nombre: 'sucursal_origen', etiqueta: 'Sucursal de origen', obligatorio: true },
  { nombre: 'dias_mora', etiqueta: 'Días de mora', obligatorio: true },
  { nombre: 'tramo_mora', etiqueta: 'Tramo de mora', obligatorio: true },
];
