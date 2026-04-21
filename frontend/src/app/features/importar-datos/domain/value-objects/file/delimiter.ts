export class Delimiter {
  private constructor(private readonly _value: DelimiterType) {}

  public static create(value: string): Delimiter {
    if (![';', ',', '|', '\t'].includes(value)) {
      throw new Error('El delimitador es inválido.');
    }

    return new Delimiter(value as DelimiterType);
  }

  value(): DelimiterType {
    return this._value;
  }
}

type DelimiterType = ';' | ',' | '|' | '\t';
