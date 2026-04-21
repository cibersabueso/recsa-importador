export class Key {
  private constructor(private readonly _value: string) {}

  static create(value: string): Key {
    if (value.trim() === '') throw new Error('La clave del archivo no puede estar vacío.');

    return new Key(value);
  }

  value(): string {
    return this._value;
  }
}
