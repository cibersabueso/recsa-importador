import {
  ChangeDetectionStrategy,
  Component,
  computed,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { Router } from '@angular/router';
import { NgClass } from '@angular/common';
import { ImportadorService } from '../../../core/services/importador.service';
import { FileBadgeComponent } from '../../../shared/components/file-badge/file-badge.component';
import { FORMATOS_ACEPTADOS, formatearTamanio } from '../../../core/models/archivo.model';

@Component({
  selector: 'app-step1-subir',
  standalone: true,
  imports: [NgClass, FileBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="paso1-grid">
      <div class="columna-principal">
        <section class="app-card">
          <header class="seccion-header">
            <div>
              <h2>Subir archivos</h2>
              <p class="subtitulo">
                Arrastra uno o varios archivos del mandante o haz clic para seleccionarlos.
              </p>
            </div>
          </header>

          <div
            class="dropzone"
            [ngClass]="{ 'dropzone--activo': arrastrando() }"
            (dragover)="onDragOver($event)"
            (dragleave)="onDragLeave($event)"
            (drop)="onDrop($event)"
            (click)="abrirSelector()"
            role="button"
            tabindex="0"
            (keydown.enter)="abrirSelector()"
          >
            <div class="dropzone-icono">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 16V4m0 0l-4 4m4-4l4 4"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
                <path
                  d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                />
              </svg>
            </div>
            <p class="dropzone-titulo">Suelta los archivos aquí</p>
            <p class="dropzone-desc">o haz clic para seleccionar desde tu equipo</p>
            <p class="dropzone-formatos">
              Formatos soportados: CSV, TXT, XLSX, XML, JSON
            </p>
            <input
              #inputFile
              type="file"
              multiple
              [accept]="formatos"
              (change)="onFileInput($event)"
              (click)="$event.stopPropagation()"
              hidden
            />
          </div>

          @if (archivos().length > 0) {
            <div class="lista-wrap">
              <h3 class="titulo-lista">
                Archivos cargados
                <span class="contador">{{ archivos().length }}</span>
              </h3>
              <ul class="lista-archivos">
                @for (archivo of archivos(); track archivo.id) {
                  <li class="item-archivo">
                    <div class="icono-archivo" [attr.data-tipo]="archivo.tipo">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          d="M7 3h7l5 5v11a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2z"
                          stroke="currentColor"
                          stroke-width="1.6"
                        />
                        <path d="M14 3v5h5" stroke="currentColor" stroke-width="1.6" />
                      </svg>
                    </div>
                    <div class="meta-archivo">
                      <div class="nombre-linea">
                        <span class="nombre-archivo">{{ archivo.nombre }}</span>
                        <app-file-badge [tipo]="archivo.tipo" />
                      </div>
                      <span class="tamanio">{{ formatearTamanio(archivo.tamanio) }}</span>
                    </div>
                    <button
                      type="button"
                      class="btn-eliminar"
                      (click)="eliminar(archivo.id, $event)"
                      aria-label="Eliminar archivo"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          d="M6 6l12 12M18 6L6 18"
                          stroke="currentColor"
                          stroke-width="2"
                          stroke-linecap="round"
                        />
                      </svg>
                    </button>
                  </li>
                }
              </ul>
            </div>
          }
        </section>

        <footer class="acciones">
          <button type="button" class="btn btn-ghost" disabled>Volver</button>
          <button
            type="button"
            class="btn btn-primary"
            [disabled]="!puedeAvanzar()"
            (click)="continuar()"
          >
            Continuar
          </button>
        </footer>
      </div>

      <aside class="panel-resumen">
        <div class="app-card resumen-card">
          <h3>Resumen</h3>
          <dl class="lista-resumen">
            <div class="fila-resumen">
              <dt>Archivos cargados</dt>
              <dd>{{ archivos().length }}</dd>
            </div>
            <div class="fila-resumen">
              <dt>Tamaño total</dt>
              <dd>{{ tamanioTotal() }}</dd>
            </div>
            <div class="fila-resumen">
              <dt>Formatos detectados</dt>
              <dd>
                @if (formatosUnicos().length === 0) {
                  <span class="vacio">—</span>
                } @else {
                  <div class="chips">
                    @for (t of formatosUnicos(); track t) {
                      <app-file-badge [tipo]="t" />
                    }
                  </div>
                }
              </dd>
            </div>
          </dl>

          <div class="tip">
            <strong>Tip:</strong> el primer archivo en orden será el archivo principal (deuda).
          </div>
        </div>
      </aside>
    </div>
  `,
  styleUrl: './step1-subir.component.scss',
})
export class Step1SubirComponent {
  private readonly importador = inject(ImportadorService);
  private readonly router = inject(Router);

  readonly formatos = FORMATOS_ACEPTADOS.join(',');
  readonly arrastrando = signal<boolean>(false);
  private readonly inputFile = viewChild<ElementRef<HTMLInputElement>>('inputFile');
  readonly archivos = this.importador.archivos;
  readonly puedeAvanzar = this.importador.puedeIrAPaso2;

  readonly tamanioTotal = computed(() => {
    const total = this.archivos().reduce((acc, a) => acc + a.tamanio, 0);
    return formatearTamanio(total);
  });

  readonly formatosUnicos = computed(() => {
    const set = new Set(this.archivos().map((a) => a.tipo));
    return Array.from(set);
  });

  readonly formatearTamanio = formatearTamanio;

  onDragOver(e: DragEvent): void {
    e.preventDefault();
    this.arrastrando.set(true);
  }

  onDragLeave(e: DragEvent): void {
    e.preventDefault();
    this.arrastrando.set(false);
  }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.arrastrando.set(false);
    const files = Array.from(e.dataTransfer?.files ?? []);
    this.procesarArchivos(files);
  }

  onFileInput(e: Event): void {
    const target = e.target as HTMLInputElement;
    const files = Array.from(target.files ?? []);
    this.procesarArchivos(files);
    target.value = '';
  }

  abrirSelector(): void {
    this.inputFile()?.nativeElement.click();
  }

  eliminar(id: string, e: Event): void {
    e.stopPropagation();
    this.importador.eliminarArchivo(id);
  }

  continuar(): void {
    if (!this.puedeAvanzar()) return;
    void this.router.navigate(['/importador/formato']);
  }

  private procesarArchivos(files: File[]): void {
    const permitidos = files.filter((f) => this.esFormatoPermitido(f.name));
    if (permitidos.length === 0) return;
    void this.importador.agregarArchivos(permitidos);
  }

  private esFormatoPermitido(nombre: string): boolean {
    const lower = nombre.toLowerCase();
    return FORMATOS_ACEPTADOS.some((ext) => lower.endsWith(ext));
  }
}
