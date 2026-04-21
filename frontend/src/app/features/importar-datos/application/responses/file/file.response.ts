export class FileResponse {
  constructor(
    public readonly id: string,
    public readonly process: string,
    public readonly name: string,
    public readonly format: string,
    public readonly size: number,
    public readonly path: string,
    public readonly separator: string | null,
    public readonly codification: string | null,
    public readonly delimiter: string | null,
    public readonly spreadsheet: number | null,
    public readonly status: boolean,
    public readonly key: string | null,
  ) {}
}
