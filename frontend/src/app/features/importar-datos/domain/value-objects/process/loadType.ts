export class LoadType {
  private constructor(private _value: string) {}

  public static create(value: string): LoadType {
    if (value.trim() === '') throw new Error('El tipo de carga no debe estar vacío');

    return new LoadType(value);
  }

  value(): string {
    return this._value;
  }
}
