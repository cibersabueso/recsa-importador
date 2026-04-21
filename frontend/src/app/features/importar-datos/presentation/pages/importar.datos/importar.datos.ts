import { Component, inject } from '@angular/core';
import { FaIconComponent } from '@fortawesome/angular-fontawesome';
import {
  faArrowUpFromBracket,
  faCheck,
  faCheckSquare,
  faCog,
  faDatabase,
  faPaperPlane,
  faFileLines,
  faXmark,
} from '@fortawesome/free-solid-svg-icons';
import { ProcessService } from '../../../infrastructure/services/process.service';
import { FileService } from '../../../infrastructure/services/file.service';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-importar-datos',
  templateUrl: './importar.datos.html',
  imports: [FaIconComponent, RouterLink],
})
export class ImportarDatos {
  faArrowUpFromBracket = faArrowUpFromBracket;
  faCog = faCog;
  faCheckSquare = faCheckSquare;
  faDatabase = faDatabase;
  faPaperPlane = faPaperPlane;
  faCheck = faCheck;
  faFileLines = faFileLines;
  faXmark = faXmark;

  private processService: ProcessService = inject(ProcessService);
  private fileService: FileService = inject(FileService);

  readonly files = this.processService.files;

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      this.addFiles(input.files);
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
  }

  onDrop(event: DragEvent) {
    event.preventDefault();

    if (event.dataTransfer?.files) {
      this.addFiles(event.dataTransfer.files);
    }
  }

  async addFiles(fileList: FileList) {
    const allowedExtensions = ['xml', 'csv', 'json', 'xlsx', 'txt'];

    const newFiles = Array.from(fileList);

    const validFiles = newFiles.filter((file) => {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
      return allowedExtensions.includes(ext);
    });

    const uniqueFiles = validFiles.filter(
      (newFile) => !this.files().some((f) => f.file.name === newFile.name),
    );

    const processId = this.processService.processId();
    if (!processId) return;

    const response = await this.fileService.save(uniqueFiles, processId);

    this.files.update((current) => [
      ...current,
      ...response.map((f) => ({ id: f.id, size: f.size, file: new File([], f.name) })),
    ]);
  }

  async deleteFile(id: string) {
    const processId = this.processService.processId();
    if (!processId) return;

    await this.fileService.delete(id);

    const data = await this.processService.getFiles(processId);

    this.files.set(data.map((f) => ({ id: f.id, size: f.size, file: new File([], f.name) })));
  }

  formatFileSize(bytes: number): string {
    if (bytes < 1024) {
      return `${bytes} Bytes`;
    }

    const kb = bytes / 1024;
    if (kb < 1024) {
      return `${kb.toFixed(2)} KB`;
    }

    const mb = kb / 1024;
    return `${mb.toFixed(2)} MB`;
  }

  getFileExtension(file: File): string {
    return file.name.split('.').pop()?.toUpperCase() ?? '';
  }
}
