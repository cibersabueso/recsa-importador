export class FileName {
  private constructor(private _value: string) {}

  public static create(value: string): FileName {
    if (value.trim() === '') throw new Error('El nombre del archivo no debe estar vacío');

    return new FileName(value);
  }

  value(): string {
    return this._value;
  }
}
