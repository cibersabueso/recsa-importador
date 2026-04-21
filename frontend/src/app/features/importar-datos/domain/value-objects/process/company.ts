export class Company {
  private constructor(private _value: string) {}

  public static create(value: string): Company {
    if (value.trim() === '') throw new Error('La empresa no debe estar vacío');

    return new Company(value);
  }

  value(): string {
    return this._value;
  }
}
