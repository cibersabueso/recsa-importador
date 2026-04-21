export class ProcessType {
  private constructor(private _value: string) {}

  public static create(value: string): ProcessType {
    if (value.trim() === '') throw new Error('El tipo de proceso no debe estar vacío');

    return new ProcessType(value);
  }

  value(): string {
    return this._value;
  }
}
