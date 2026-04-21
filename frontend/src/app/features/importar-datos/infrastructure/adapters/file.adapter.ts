import { HttpClient } from '@angular/common/http';
import type { File } from '../../domain/entities/file';
import type { FileRepository } from '../../domain/ports/file.port';
import type { FileId } from '../../domain/value-objects/file/fileId';
import type { FilePreview } from '../../domain/value-objects/file/filePreview';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../../environments/environment';
import { FileFactory } from '../../domain/factories/file.factory';
import { UpdateFileDTO } from '../../application/dtos/file/updateFileDTO';

@Injectable({ providedIn: 'root' })
export class FileAdapter implements FileRepository {
  private http: HttpClient = inject(HttpClient);

  async uploadFiles(files: globalThis.File[], process: string): Promise<File[]> {
    const data = new FormData();
    files.forEach((file) => data.append('files[]', file));
    data.append('process_config', process);

    const response = await firstValueFrom(
      this.http.post<{
        message: string;
        data: {
          id: string;
          fileName: string;
          fileFormat: string;
          fileSize: number;
          storagePath: string;
          processConfig: string;
          decimalSeparator: null;
          fileEncoding: null;
          fileDelimiter: null;
          spreadsheet: null;
          firstRowHeaders: true;
          fileStatus: string;
        }[];
      }>(`${environment.apiUrl}/import-file`, data),
    );

    return response.data.map((resp) =>
      FileFactory.fromPrimitives(
        resp.id,
        resp.processConfig,
        resp.fileName,
        resp.fileFormat,
        resp.fileSize,
        resp.storagePath,
        resp.fileDelimiter,
        resp.fileEncoding,
        resp.decimalSeparator,
        resp.spreadsheet,
        false,
        null,
      ),
    );
  }

  async updateFile(file: File): Promise<File> {

    const id = file.id();
    if(id === null) throw new Error("El archivo no tiene ID.");

    const dto = new UpdateFileDTO(
      file.name().value(),
      file.format().value(),
      file.path().value(),
      file.size().value(),
      file.separator()?.value() ?? '',
      file.codification()?.value() ?? '',
      file.delimiter()?.value() ?? null,
      file.spreadsheet()?.value() ?? null,
      true,
      file.process().value(),
      file.key()?.value() ?? null,
      0
    );
    const data = await firstValueFrom(this.http.put<any>(`${environment.apiUrl}/import-file/${id.value()}`, dto));

    console.log(data);
    throw new Error('Method not implemented.' + file.name);
  }

  async previewFile(id: FileId): Promise<FilePreview> {
    throw new Error('Method not implemented.' + id);
  }

  async deleteFile(id: FileId): Promise<void> {
    await firstValueFrom(this.http.delete<void>(`${environment.apiUrl}/import-file/${id.value()}`));
  }
}
