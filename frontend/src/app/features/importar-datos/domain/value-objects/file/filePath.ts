export class FilePath {
  private constructor(private _value: string) {}

  public static create(value: string): FilePath {
    if (value.trim() === '') throw new Error('La ruta del archivo no debe estar vacío');

    return new FilePath(value);
  }

  value(): string {
    return this._value;
  }
}
