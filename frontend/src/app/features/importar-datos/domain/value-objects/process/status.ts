export class Status {
  private constructor(private readonly _value: StatusType) {}

  public static create(value: string): Status {
    if (!['Pendiente', 'Procesando', 'Pausado', 'Detenido', 'Finalizado'].includes(value)) {
      throw new Error('LEl estado del proceso es inválido.');
    }

    return new Status(value as StatusType);
  }

  value(): StatusType {
    return this._value;
  }
}

type StatusType = 'Pendiente' | 'Procesando' | 'Pausado' | 'Detenido' | 'Finalizado';
