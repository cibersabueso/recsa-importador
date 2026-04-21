import type { ProcessRepository } from '../../domain/ports/proces.port';
import { ProcessId } from '../../domain/value-objects/process/processId';
import { ProcessResponse } from '../responses/process/process.response';

export class GetProcessUseCase {
  constructor(private readonly repository: ProcessRepository) {}

  async exec(id: string): Promise<ProcessResponse> {
    const entity = await this.repository.showProcess(ProcessId.create(id));

    return new ProcessResponse(
      id,
      entity.company()?.value() ?? null,
      entity.loadType()?.value() ?? null,
      entity.processType()?.value() ?? null,
      entity.layoutName()?.value() ?? null,
      entity.responsible()?.value() ?? null,
      entity.status().value(),
    );
  }
}
