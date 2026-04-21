import type { OnInit } from '@angular/core';
import { Component, inject, signal } from '@angular/core';
import { FaIconComponent } from '@fortawesome/angular-fontawesome';
import {
  faCity,
  faDiagramProject,
  faArrowUpFromBracket,
  faDatabase,
  faSave,
  faSliders,
  faHashtag,
  faAngleUp,
  faAngleDown,
  faFileLines,
  faAngleLeft,
  faCheck,
} from '@fortawesome/free-solid-svg-icons';
import { ProcessService } from '../../../infrastructure/services/process.service';
import { RouterLink } from '@angular/router';
import { SaveProcessRequest } from '../../../infrastructure/requests/save.process.request';
import { FormsModule } from '@angular/forms';
import { toObservable } from '@angular/core/rxjs-interop';
import { filter, switchMap } from 'rxjs/operators';
import { ConfigurarArchivo } from '../../components/configurar.archivo/configurar.archivo';

@Component({
  selector: 'app-configurar-datos',
  templateUrl: './configurar.formato.html',
  imports: [FaIconComponent, RouterLink, FormsModule, ConfigurarArchivo],
})
export class ConfigurarFormato implements OnInit {
  constructor() {
    // Convertir la señal a Observable
    toObservable(this.processId)
      .pipe(
        // Filtrar solo cuando NO sea null
        filter((id): id is string => id !== null),
        // Hacer la petición cada vez que cambie el ID
        switchMap(() => this.processService.getCurrentProcess()),
      )
      .subscribe(() => {
        this.form.set({
          company: this.currentProcess()?.company ?? '',
          load_type: this.currentProcess()?.load_type ?? '',
          layout_name: this.currentProcess()?.layout_name ?? '',
          process_type: this.currentProcess()?.process_type ?? '',
          responsible: this.currentProcess()?.responsible ?? '',
        });
      });
  }

  faDiagramProject = faDiagramProject;
  faCity = faCity;
  faArrowUpFromBracket = faArrowUpFromBracket;
  faDatabase = faDatabase;
  faSave = faSave;
  faSliders = faSliders;
  faHashtag = faHashtag;
  faAngleUp = faAngleUp;
  faAngleDown = faAngleDown;
  faFileLines = faFileLines;
  faAngleLeft = faAngleLeft;
  faCheck = faCheck;

  private processService = inject(ProcessService);

  readonly files = this.processService.files;
  readonly processId = this.processService.processId;
  readonly companies = this.processService.companies;
  readonly loadTypes = this.processService.loadTypes;
  readonly layouts = this.processService.layouts;
  readonly processTypes = this.processService.processTypes;
  readonly currentProcess = this.processService.currentProcess;

  spinSave = signal<boolean>(false);

  readonly form = signal<{
    company: string;
    load_type: string;
    process_type: string;
    layout_name: string;
    responsible: string;
  }>({
    company: '',
    load_type: '',
    process_type: '',
    layout_name: '',
    responsible: '',
  });

  async ngOnInit() {
    await Promise.all([
      this.processService.getCompanies(),
      this.processService.getLoadType(),
      this.processService.getLayouts(),
      this.processService.getProcessTypes(),
    ]);
  }

  getFileExtension(file: File): string {
    return file.name.split('.').pop()?.toUpperCase() ?? '';
  }

  async configureProcess(): Promise<void> {
    const id = this.processId();
    if (!id) return;

    const request = new SaveProcessRequest(
      this.form().company,
      this.form().load_type,
      this.form().process_type,
      this.form().layout_name,
      this.form().responsible,
    );

    await this.processService.configure(request, id);

    this.spinSave.set(true);
    setInterval(() => this.spinSave.set(false), 1000);
  }
}
