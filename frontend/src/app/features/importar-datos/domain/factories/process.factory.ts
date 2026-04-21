import { Process } from '../entities/process';
import { Company } from '../value-objects/process/company';
import { LayoutName } from '../value-objects/process/layoutName';
import { LoadType } from '../value-objects/process/loadType';
import { ProcessId } from '../value-objects/process/processId';
import { ProcessType } from '../value-objects/process/processType';
import { Responsible } from '../value-objects/process/responsible';
import { Status } from '../value-objects/process/status';

export class ProcessFactory {
  static fromPrimitives(
    id: string | null,
    company: string | null,
    loadType: string | null,
    processType: string | null,
    layoutName: string | null,
    responsible: string | null,
    status: string | null,
  ): Process {
    return Process.create(
      id ? ProcessId.create(id) : null,
      company ? Company.create(company) : null,
      loadType ? LoadType.create(loadType) : null,
      processType ? ProcessType.create(processType) : null,
      layoutName ? LayoutName.create(layoutName) : null,
      responsible ? Responsible.create(responsible) : null,
      status ? Status.create(status) : Status.create('Pendiente'),
    );
  }
}
