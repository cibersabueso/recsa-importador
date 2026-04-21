export class Codification {
  private constructor(private readonly _value: CodificationType) {}

  public static create(value: string): Codification {
    if (!['UTF-8', 'Latin1', 'Windows-1252'].includes(value)) {
      throw new Error('La condificación es inválido.');
    }

    return new Codification(value as CodificationType);
  }

  value(): CodificationType {
    return this._value;
  }
}

type CodificationType = 'UTF-8' | 'Latin1' | 'Windows-1252';
