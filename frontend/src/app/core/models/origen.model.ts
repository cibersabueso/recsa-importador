export type TipoOrigen = 'sftp' | 'correo' | 'teams';

export interface OrigenSftp {
  tipo: 'sftp';
  host: string;
  puerto: number;
  usuario: string;
  password: string;
  ruta: string;
}

export interface OrigenCorreo {
  tipo: 'correo';
  direccion: string;
  carpeta: string;
}

export interface OrigenTeams {
  tipo: 'teams';
  equipo: string;
  canal: string;
}

export type OrigenDatos = OrigenSftp | OrigenCorreo | OrigenTeams;

export const ORIGEN_VACIO_SFTP: OrigenSftp = {
  tipo: 'sftp',
  host: '',
  puerto: 22,
  usuario: '',
  password: '',
  ruta: '',
};

export const ORIGEN_VACIO_CORREO: OrigenCorreo = {
  tipo: 'correo',
  direccion: '',
  carpeta: '',
};

export const ORIGEN_VACIO_TEAMS: OrigenTeams = {
  tipo: 'teams',
  equipo: '',
  canal: '',
};

export function crearOrigenVacio(tipo: TipoOrigen): OrigenDatos {
  if (tipo === 'sftp') return { ...ORIGEN_VACIO_SFTP };
  if (tipo === 'correo') return { ...ORIGEN_VACIO_CORREO };
  return { ...ORIGEN_VACIO_TEAMS };
}

export function esOrigenCompleto(origen: OrigenDatos | null): boolean {
  if (origen === null) return false;
  if (origen.tipo === 'sftp') {
    return (
      origen.host.trim() !== '' &&
      Number.isFinite(origen.puerto) &&
      origen.puerto > 0 &&
      origen.usuario.trim() !== '' &&
      origen.password.trim() !== '' &&
      origen.ruta.trim() !== ''
    );
  }
  if (origen.tipo === 'correo') {
    const correoValido = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(origen.direccion.trim());
    return correoValido && origen.carpeta.trim() !== '';
  }
  return origen.equipo.trim() !== '' && origen.canal.trim() !== '';
}

export interface OpcionOrigen {
  tipo: TipoOrigen;
  titulo: string;
  descripcion: string;
}

export const OPCIONES_ORIGEN: readonly OpcionOrigen[] = [
  {
    tipo: 'sftp',
    titulo: 'SFTP',
    descripcion: 'Servidor de transferencia de archivos seguro',
  },
  {
    tipo: 'correo',
    titulo: 'Correo electrónico',
    descripcion: 'Buzón con adjuntos de carga periódica',
  },
  {
    tipo: 'teams',
    titulo: 'Microsoft Teams',
    descripcion: 'Canal de equipo con archivos compartidos',
  },
];
