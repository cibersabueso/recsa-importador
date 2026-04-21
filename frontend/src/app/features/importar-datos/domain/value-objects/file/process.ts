export class Process {
  private constructor(private _value: string) {}

  public static create(value: string): Process {
    if (value.trim() === '') throw new Error('El id del proceso no debe estar vacío');

    return new Process(value);
  }

  value(): string {
    return this._value;
  }
}
