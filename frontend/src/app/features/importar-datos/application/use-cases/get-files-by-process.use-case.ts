import type { ProcessRepository } from '../../domain/ports/proces.port';
import { ProcessId } from '../../domain/value-objects/process/processId';
import type { FileResponse } from '../responses/file/file.response';

export class GetFilesByProcessUseCase {
  constructor(private readonly repository: ProcessRepository) {}

  async exec(id: string): Promise<FileResponse[]> {
    const files = await this.repository.getFilesByProcess(ProcessId.create(id));

    return files.map((file) => ({
      id: file.id()?.value() ?? '',
      process: file.process().value(),
      name: file.name().value(),
      format: file.format().value(),
      size: file.size().value(),
      path: file.path().value(),
      delimiter: file.delimiter()?.value() ?? null,
      codification: file.codification()?.value() ?? null,
      separator: file.separator()?.value() ?? null,
      spreadsheet: file.spreadsheet()?.value() ?? null,
      status: file.isConfigurated(),
      key: file.key()?.value() ?? null,
    }));
  }
}
