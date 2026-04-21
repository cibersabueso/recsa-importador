export class FileFormat {
  private constructor(private readonly _value: FileFormatType) {}

  public static create(value: string): FileFormat {
    if (!['CSV', 'XLSX', 'TXT', 'JSON', 'XML'].includes(value.toUpperCase())) {
      throw new Error('La condificación es inválido.');
    }

    return new FileFormat(value as FileFormatType);
  }

  value(): FileFormatType {
    return this._value;
  }
}

type FileFormatType = 'CSV' | 'XLSX' | 'TXT' | 'JSON' | 'XML';
