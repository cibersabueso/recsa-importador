import { Process } from '../../domain/entities/process';
import { Company } from '../../domain/value-objects/process/company';
import { LayoutName } from '../../domain/value-objects/process/layoutName';
import { LoadType } from '../../domain/value-objects/process/loadType';
import { ProcessId } from '../../domain/value-objects/process/processId';
import { ProcessType } from '../../domain/value-objects/process/processType';
import { Responsible } from '../../domain/value-objects/process/responsible';
import { Status } from '../../domain/value-objects/process/status';
import type { ProcessDTO } from '../dtos/process.dto';
import { SaveProcessRequest } from '../requests/save.process.request';

export class ProcessMapper {
  static dtoToEntity(dto: ProcessDTO): Process {
    return Process.create(
      ProcessId.create(dto.id),
      dto.company ? Company.create(dto.company) : null,
      dto.loadType ? LoadType.create(dto.loadType) : null,
      dto.company ? ProcessType.create(dto.company) : null,
      dto.processType ? LayoutName.create(dto.processType) : null,
      dto.responsible ? Responsible.create(dto.responsible) : null,
      Status.create('Pendiente'),
    );
  }

  static entityToSaveRequest(entity: Process): SaveProcessRequest {
    return new SaveProcessRequest(
      entity.company()?.value() ?? null,
      entity.loadType()?.value() ?? null,
      entity.processType()?.value() ?? null,
      entity.layoutName()?.value() ?? null,
      entity.responsible()?.value() ?? null,
    );
  }
}
