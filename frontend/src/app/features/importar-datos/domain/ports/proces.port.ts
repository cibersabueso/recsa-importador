import type { File } from '../entities/file';
import type { Process } from '../entities/process';
import type { ProcessId } from '../value-objects/process/processId';

export interface ProcessRepository {
  saveProcess(entity: Process): Promise<Process>;
  updateProcess(entity: Process, id: string): Promise<Process>;
  findProcess(): Promise<Process | null>;
  showProcess(id: ProcessId): Promise<Process>;
  getFilesByProcess(id: ProcessId): Promise<File[]>;
}
