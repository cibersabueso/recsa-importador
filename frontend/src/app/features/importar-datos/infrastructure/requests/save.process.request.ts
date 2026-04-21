export class SaveProcessRequest {
  constructor(
    public readonly company: string | null,
    public readonly load_type: string | null,
    public readonly process_type: string | null,
    public readonly layout: string | null,
    public readonly responsible: string | null,
  ) {}
}
