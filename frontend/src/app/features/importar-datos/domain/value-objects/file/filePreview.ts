export class FilePreview {
  private constructor(
    private readonly _headers: string[],
    private readonly _data: string[][],
  ) {}

  static create(headers: string[], data: string[][]): FilePreview {
    return new FilePreview(headers, data);
  }

  headers(): string[] {
    return this._headers;
  }

  data(): string[][] {
    return this._data;
  }
}
