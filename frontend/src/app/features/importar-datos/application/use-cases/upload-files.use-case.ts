import type { File } from '../../domain/entities/file';
import type { FileRepository } from '../../domain/ports/file.port';
import type { UploadFilesDTO } from '../dtos/file/upload-files.dto';

export class UploadFilesUseCase {
  constructor(private readonly repository: FileRepository) {}

  async exec(files: UploadFilesDTO, process: string): Promise<File[]> {
    const data = await this.repository.uploadFiles(files.files, process);

    return data;
  }
}
