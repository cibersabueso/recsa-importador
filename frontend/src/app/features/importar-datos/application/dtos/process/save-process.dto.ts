export class SaveProcessDTO {
  constructor(
    public readonly company: string | null,
    public readonly loadType: string | null,
    public readonly processType: string | null,
    public readonly layout: string | null,
    public readonly responsible: string | null,
  ) {}
}
