import { inject, Injectable, signal } from '@angular/core';
import { SaveProcessUseCase } from '../../application/use-cases/save-process.use-case';
import { ProcessDTO } from '../dtos/process.dto';
import { ProcessAdapter } from '../adapters/process.adapter';
import type { SaveProcessRequest } from '../requests/save.process.request';
import { SaveProcessDTO } from '../../application/dtos/process/save-process.dto';
import { GetFilesByProcessUseCase } from '../../application/use-cases/get-files-by-process.use-case';
import { FileDTO } from '../dtos/file.dto';
import { ConfigureProcessUseCase } from '../../application/use-cases/configureProcess.useCase';
import { firstValueFrom } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ProcessService {
  private http: HttpClient = inject(HttpClient);
  private repository = inject(ProcessAdapter);
  private saveUseCase: SaveProcessUseCase = new SaveProcessUseCase(this.repository);
  private getFilesUseCase: GetFilesByProcessUseCase = new GetFilesByProcessUseCase(this.repository);
  private configureUseCase: ConfigureProcessUseCase = new ConfigureProcessUseCase(this.repository);

  readonly files = signal<
    {
      id: string | null;
      size: number;
      file: File;
    }[]
  >([]);

  readonly processId = signal<string | null>(null);
  readonly currentStep = signal<1 | 2 | 3 | 4 | 5>(1);
  readonly companies = signal<{ id: string; name: string }[]>([]);
  readonly loadTypes = signal<{ id: string; name: string }[]>([]);
  readonly layouts = signal<{ id: string; name: string }[]>([]);
  readonly processTypes = signal<{ id: string; name: string }[]>([]);
  readonly currentProcess = signal<{
    id: string;
    company: string;
    load_type: string;
    layout_name: string;
    process_type: string;
    responsible: string;
  } | null>(null);

  async save(request: SaveProcessRequest): Promise<ProcessDTO> {
    const dto = new SaveProcessDTO(
      request.company,
      request.load_type,
      request.process_type,
      request.layout,
      request.responsible,
    );
    const response = await this.saveUseCase.exec(dto);

    return new ProcessDTO(
      response.id,
      response.company,
      response.load_type,
      response.process_type,
      response.layout_name,
      response.responsible,
    );
  }

  async getFiles(id: string): Promise<FileDTO[]> {
    const response = await this.getFilesUseCase.exec(id);

    return response.map(
      (file) =>
        new FileDTO(
          file.id,
          file.process,
          file.name,
          file.format,
          file.size,
          file.path,
          file.delimiter,
          file.codification,
          file.separator,
          file.spreadsheet,
          file.status,
          file.key,
        ),
    );
  }

  async configure(request: SaveProcessRequest, id: string): Promise<ProcessDTO> {
    const dto = new SaveProcessDTO(
      request.company,
      request.load_type,
      request.process_type,
      request.layout,
      request.responsible,
    );
    const response = await this.configureUseCase.exec(dto, id);

    return new ProcessDTO(
      response.id,
      response.company,
      response.load_type,
      response.process_type,
      response.layout_name,
      response.responsible,
    );
  }

  async getCurrentProcess(): Promise<void> {
    const process = await firstValueFrom(
      this.http.get<{
        id: string;
        company: string | null;
        loadType: string | null;
        layout: string | null;
        processType: string | null;
        responsible: string | null;
      }>(`${environment.apiUrl}/process-config/${this.processId()}`),
    );

    this.currentProcess.set({
      id: process.id,
      company: process.company ?? '',
      load_type: process.loadType ?? '',
      layout_name: process.layout ?? '',
      process_type: process.processType ?? '',
      responsible: process.responsible ?? '',
    });
  }

  async getCompanies(): Promise<void> {
    const companies = await firstValueFrom(
      this.http.get<{ companies: { id: string; name: string }[] }>(`${environment.apiUrl}/company`),
    );
    this.companies.set(companies.companies);
  }

  async getLoadType(): Promise<void> {
    const loadTypes = await firstValueFrom(
      this.http.get<{ loadTypes: { id: string; name: string }[] }>(
        `${environment.apiUrl}/load-type`,
      ),
    );
    this.loadTypes.set(loadTypes.loadTypes);
  }

  async getLayouts(): Promise<void> {
    const layouts = await firstValueFrom(
      this.http.get<{ layouts: { id: string; name: string }[] }>(`${environment.apiUrl}/layout`),
    );
    this.layouts.set(layouts.layouts);
  }

  async getProcessTypes(): Promise<void> {
    this.processTypes.set([
      { id: 'Flujo', name: 'Flujo' },
      { id: 'Refresco', name: 'Refresco' },
    ]);
  }
}
