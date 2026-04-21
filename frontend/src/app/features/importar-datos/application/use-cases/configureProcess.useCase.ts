import { ProcessFactory } from '../../domain/factories/process.factory';
import type { ProcessRepository } from '../../domain/ports/proces.port';
import type { SaveProcessDTO } from '../dtos/process/save-process.dto';
import { ProcessResponse } from '../responses/process/process.response';

export class ConfigureProcessUseCase {
  constructor(private readonly repository: ProcessRepository) {}

  async exec(dto: SaveProcessDTO, id: string): Promise<ProcessResponse> {
    const entity = await this.repository.updateProcess(
      ProcessFactory.fromPrimitives(
        id,
        dto.company,
        dto.loadType,
        dto.processType,
        dto.layout,
        dto.responsible,
        'Pendiente',
      ),
      id,
    );

    return new ProcessResponse(
      id,
      entity.company()?.value() ?? null,
      entity.loadType()?.value() ?? null,
      entity.processType()?.value() ?? null,
      entity.layoutName()?.value() ?? null,
      entity.responsible()?.value() ?? null,
      entity.status().value() ?? null,
    );
  }
}
