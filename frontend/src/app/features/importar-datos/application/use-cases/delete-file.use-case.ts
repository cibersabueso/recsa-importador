import type { FileRepository } from '../../domain/ports/file.port';
import { FileId } from '../../domain/value-objects/file/fileId';

export class DeleteFileUseCase {
  constructor(private readonly repository: FileRepository) {}

  async exec(id: string): Promise<void> {
    await this.repository.deleteFile(FileId.create(id));
  }
}
