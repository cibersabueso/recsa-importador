import { ProcessFactory } from '../../domain/factories/process.factory';
import type { ProcessRepository } from '../../domain/ports/proces.port';
import type { SaveProcessDTO } from '../dtos/process/save-process.dto';
import { ProcessResponse } from '../responses/process/process.response';

export class SaveProcessUseCase {
  constructor(private readonly repository: ProcessRepository) {}

  async exec(dto: SaveProcessDTO): Promise<ProcessResponse> {
    const entity = ProcessFactory.fromPrimitives(
      null,
      dto.company,
      dto.loadType,
      dto.processType,
      dto.layout,
      dto.responsible,
      'Pendiente',
    );
    const response = await this.repository.saveProcess(entity);

    const id = response.id();
    if (!id) throw new Error('Hubo un error al guardar el proceso.');

    return new ProcessResponse(
      id.value(),
      response.company()?.value() ?? null,
      response.loadType()?.value() ?? null,
      response.processType()?.value() ?? null,
      response.layoutName()?.value() ?? null,
      response.responsible()?.value() ?? null,
      response.status().value(),
    );
  }
}
