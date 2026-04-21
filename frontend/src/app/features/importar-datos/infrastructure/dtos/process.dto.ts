export class ProcessDTO {
  constructor(
    public readonly id: string,
    public readonly company: string | null,
    public readonly loadType: string | null,
    public readonly processType: string | null,
    public readonly layout: string | null,
    public readonly responsible: string | null,
  ) {}
}
