export class FileId {
  private constructor(private _value: string) {}

  public static create(value: string): FileId {
    if (value.trim() === '') throw new Error('El id del archivo no debe estar vacío');

    return new FileId(value);
  }

  value(): string {
    return this._value;
  }
}
