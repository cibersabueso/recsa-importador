export class LayoutName {
  private constructor(private _value: string) {}

  public static create(value: string): LayoutName {
    if (value.trim() === '') throw new Error('El nombre de la interfaz no debe estar vacío');

    return new LayoutName(value);
  }

  value(): string {
    return this._value;
  }
}
