import type { Company } from '../value-objects/process/company';
import type { LayoutName } from '../value-objects/process/layoutName';
import type { LoadType } from '../value-objects/process/loadType';
import type { ProcessId } from '../value-objects/process/processId';
import type { ProcessType } from '../value-objects/process/processType';
import type { Responsible } from '../value-objects/process/responsible';
import type { Status } from '../value-objects/process/status';

export class Process {
  private constructor(
    private readonly _id: ProcessId | null,
    private readonly _company: Company | null,
    private readonly _loadType: LoadType | null,
    private readonly _processType: ProcessType | null,
    private readonly _layoutName: LayoutName | null,
    private readonly _responsible: Responsible | null,
    private readonly _status: Status,
  ) {}

  static create(
    id: ProcessId | null,
    company: Company | null,
    loadType: LoadType | null,
    processType: ProcessType | null,
    layoutName: LayoutName | null,
    responsible: Responsible | null,
    status: Status,
  ): Process {
    if (!id && !company && !loadType && !processType && !layoutName && !responsible && !status)
      throw new Error('El proceso no debe estar vacío.');

    return new Process(id, company, loadType, processType, layoutName, responsible, status);
  }

  id(): ProcessId | null {
    return this._id;
  }

  company(): Company | null {
    return this._company;
  }

  loadType(): LoadType | null {
    return this._loadType;
  }

  processType(): ProcessType | null {
    return this._processType;
  }

  layoutName(): LayoutName | null {
    return this._layoutName;
  }

  responsible(): Responsible | null {
    return this._responsible;
  }

  status(): Status {
    return this._status;
  }
}
