export class ProcessId {
  private constructor(private _value: string) {}

  public static create(value: string): ProcessId {
    if (value.trim() === '') throw new Error('El id del proceso no debe estar vacío');

    return new ProcessId(value);
  }

  value(): string {
    return this._value;
  }
}
