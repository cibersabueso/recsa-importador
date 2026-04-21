export class DecimalSeparator {
  private constructor(private readonly _value: DecimalSeparatorType) {}

  public static create(value: string): DecimalSeparator {
    if (!['.', ','].includes(value)) {
      throw new Error('El separador decimal es inválido.');
    }

    return new DecimalSeparator(value as DecimalSeparatorType);
  }

  value(): DecimalSeparatorType {
    return this._value;
  }
}

type DecimalSeparatorType = '.' | ',';
