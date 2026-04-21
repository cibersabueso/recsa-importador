import type { File } from '../entities/file';
import type { FileId } from '../value-objects/file/fileId';
import type { FilePreview } from '../value-objects/file/filePreview';

export interface FileRepository {
  uploadFiles(files: globalThis.File[], process: string): Promise<File[]>;
  updateFile(file: File): Promise<File>;
  previewFile(id: FileId): Promise<FilePreview>;
  deleteFile(id: FileId): Promise<void>;
}
