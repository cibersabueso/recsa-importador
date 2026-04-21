export class ProcessResponse {
  constructor(
    public readonly id: string,
    public readonly company: string | null,
    public readonly load_type: string | null,
    public readonly process_type: string | null,
    public readonly layout_name: string | null,
    public readonly responsible: string | null,
    public readonly status: string | null,
  ) {}
}
