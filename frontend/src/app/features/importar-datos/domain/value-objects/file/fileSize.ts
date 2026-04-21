export class FileSize {
  private constructor(private _value: number) {}

  public static create(value: number): FileSize {
    if (value <= 0) throw new Error('El tamaño del archivo debe ser mayor a cero.');

    return new FileSize(value);
  }

  value(): number {
    return this._value;
  }
}
