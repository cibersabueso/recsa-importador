export class SpreadSheet {
  private constructor(private _value: number) {}

  public static create(value: number): SpreadSheet {
    if (value < 0) throw new Error('la hoja del archivo es inválido');

    return new SpreadSheet(value);
  }

  value(): number {
    return this._value;
  }
}
