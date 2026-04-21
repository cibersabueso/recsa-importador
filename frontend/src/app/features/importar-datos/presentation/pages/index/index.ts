import type { OnInit } from '@angular/core';
import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ProcessService } from '../../../infrastructure/services/process.service';
import { ImportarDatosHeader } from '../../components/header/header';
import { ImportDatasSummary } from '../../components/summary/summary';

@Component({
  selector: 'app-importar-datos-index',
  templateUrl: './index.html',
  imports: [RouterOutlet, ImportarDatosHeader, ImportDatasSummary],
})
export class ImportarDatosIndex implements OnInit {
  private service: ProcessService = inject(ProcessService);

  readonly files = this.service.files;
  readonly processId = this.service.processId;

  async ngOnInit() {
    const processId = localStorage.getItem('process_id');
    if (processId) {
      const data = await this.service.getFiles(processId);
      this.processId.set(processId);
      this.service.files.set(
        data.map((f) => ({ id: f.id, size: f.size, file: new File([], f.name) })),
      );
    } else {
      const response = await this.service.save({
        company: null,
        layout: null,
        load_type: null,
        process_type: null,
        responsible: null,
      });
      localStorage.setItem('process_id', response.id);
      this.processId.set(response.id);
    }
  }
}
