export class Responsible {
  private constructor(private _value: string) {}

  public static create(value: string): Responsible {
    if (value.trim() === '') throw new Error('El responsable no debe estar vacío');

    return new Responsible(value);
  }

  value(): string {
    return this._value;
  }
}
