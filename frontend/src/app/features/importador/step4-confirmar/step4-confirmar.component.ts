import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { NgClass } from '@angular/common';
import { ImportadorService } from '../../../core/services/importador.service';
import { FileBadgeComponent } from '../../../shared/components/file-badge/file-badge.component';
import { Delimitador } from '../../../core/models/archivo.model';

@Component({
  selector: 'app-step4-confirmar',
  standalone: true,
  imports: [NgClass, FileBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="paso4">
      @if (resultado() === null) {
        <section class="app-card seccion">
          <header class="seccion-header">
            <div>
              <h2>Confirmar importación</h2>
              <p class="subtitulo">
                Revisa el resumen antes de procesar los archivos en el sistema RECSA.
              </p>
            </div>
          </header>

          <div class="grid-stats">
            <div class="stat-card stat-exito">
              <span class="stat-label">Filas válidas</span>
              <span class="stat-num">{{ formato(estimadas().validas) }}</span>
              <span class="stat-desc">Registros listos para cargar</span>
            </div>
            <div class="stat-card stat-error">
              <span class="stat-label">Filas con error</span>
              <span class="stat-num">{{ formato(estimadas().errores) }}</span>
              <span class="stat-desc">Campos obligatorios vacíos o inválidos</span>
            </div>
            <div class="stat-card stat-neutro">
              <span class="stat-label">Duplicados</span>
              <span class="stat-num">{{ formato(estimadas().duplicados) }}</span>
              <span class="stat-desc">Registros repetidos por columna clave</span>
            </div>
          </div>

          @if (estimadas().errores > 0) {
            <div class="alert alert-warning">
              <strong>Atención:</strong> hay {{ formato(estimadas().errores) }} filas con error.
              Serán reportadas al finalizar la importación pero no se cargarán al sistema.
            </div>
          }
        </section>

        <section class="app-card seccion">
          <header class="seccion-header">
            <div>
              <h3>Archivos a procesar</h3>
              <p class="subtitulo">Detalle por archivo en el orden de procesamiento.</p>
            </div>
          </header>

          <ul class="lista-archivos-final">
            @for (a of archivos(); track a.id; let idx = $index) {
              <li class="fila-archivo">
                <div class="orden">{{ a.orden }}</div>
                <div class="info">
                  <div class="nombre-linea">
                    <span class="nombre">{{ a.nombre }}</span>
                    <app-file-badge [tipo]="a.tipo" />
                    @if (idx === 0) {
                      <span class="badge-principal">Principal</span>
                    }
                  </div>
                  <div class="badges-detalle">
                    <span class="badge-info">
                      Separador: <strong>{{ etiquetaDelim(a.delimitador) }}</strong>
                    </span>
                    <span class="badge-info">
                      Clave: <strong>{{ a.columnaClave ?? '—' }}</strong>
                    </span>
                    @if (a.columnaJoin && a.columnaJoin !== a.columnaClave) {
                      <span class="badge-info">
                        Join: <strong>{{ a.columnaJoin }}</strong>
                      </span>
                    }
                    <span class="badge-info">
                      Encoding: <strong>{{ a.codificacion }}</strong>
                    </span>
                  </div>
                </div>
                <div class="conteos">
                  <div class="conteo">
                    <span class="conteo-num ok">{{ formato(estimarValidas(a.id)) }}</span>
                    <span class="conteo-label">válidas</span>
                  </div>
                  <div class="conteo">
                    <span class="conteo-num error">{{ formato(estimarErrores(a.id, idx)) }}</span>
                    <span class="conteo-label">error</span>
                  </div>
                  <div class="conteo">
                    <span class="conteo-num neutro">{{ formato(estimarDuplicados(a.id)) }}</span>
                    <span class="conteo-label">dup.</span>
                  </div>
                </div>
              </li>
            }
          </ul>
        </section>

        <footer class="acciones">
          <button type="button" class="btn btn-ghost" (click)="volver()" [disabled]="procesando()">
            Volver
          </button>
          <button
            type="button"
            class="btn btn-primary btn-procesar"
            [disabled]="procesando()"
            (click)="procesar()"
          >
            @if (procesando()) {
              <span>Procesando...</span>
            } @else {
              <span>Procesar importación</span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M22 2L11 13"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
                <path
                  d="M22 2l-7 20-4-9-9-4 20-7z"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            }
          </button>
        </footer>
      } @else {
        <section class="app-card seccion seccion-exito">
          <div class="icono-exito">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" />
              <path
                d="M8 12l3 3 5-6"
                stroke="currentColor"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </div>
          <h2>Importación procesada</h2>
          <p class="subtitulo centro">
            Job: <strong>{{ resultado()!.jobId }}</strong>
          </p>

          <div class="grid-stats">
            <div class="stat-card stat-exito">
              <span class="stat-label">Filas válidas</span>
              <span class="stat-num">{{ formato(resultado()!.filasValidas) }}</span>
            </div>
            <div class="stat-card stat-error">
              <span class="stat-label">Filas con error</span>
              <span class="stat-num">{{ formato(resultado()!.filasConError) }}</span>
            </div>
            <div class="stat-card stat-neutro">
              <span class="stat-label">Duplicados</span>
              <span class="stat-num">{{ formato(resultado()!.duplicados) }}</span>
            </div>
          </div>

          <div class="acciones centro">
            <button type="button" class="btn btn-primary" (click)="nuevaImportacion()">
              Nueva importación
            </button>
          </div>
        </section>
      }
    </div>
  `,
  styleUrl: './step4-confirmar.component.scss',
})
export class Step4ConfirmarComponent {
  private readonly importador = inject(ImportadorService);
  private readonly router = inject(Router);

  readonly archivos = this.importador.archivos;
  readonly resultado = this.importador.resultado;
  readonly procesando = signal<boolean>(false);

  private readonly _resultadoLocal = signal<ReturnType<ImportadorService['calcularEstadisticasEstimadas']> | null>(null);

  readonly estimadas = computed(
    () => this._resultadoLocal() ?? this.importador.calcularEstadisticasEstimadas(),
  );

  constructor() {
    this._resultadoLocal.set(this.importador.calcularEstadisticasEstimadas());
  }

  formato(n: number): string {
    return n.toLocaleString('es-PE');
  }

  etiquetaDelim(valor: Delimitador): string {
    switch (valor) {
      case ';':
        return 'Punto y coma';
      case ',':
        return 'Coma';
      case '|':
        return 'Barra vertical';
      case '\t':
        return 'Tabulación';
      default:
        return valor;
    }
  }

  estimarValidas(_id: string): number {
    const archivos = this.archivos();
    if (archivos.length === 0) return 0;
    return Math.floor(this.estimadas().validas / archivos.length);
  }

  estimarErrores(_id: string, idx: number): number {
    const archivos = this.archivos();
    if (archivos.length === 0) return 0;
    return idx === 0 ? this.estimadas().errores : 0;
  }

  estimarDuplicados(_id: string): number {
    const archivos = this.archivos();
    if (archivos.length === 0) return 0;
    return Math.floor(this.estimadas().duplicados / archivos.length);
  }

  procesar(): void {
    this.procesando.set(true);
    this.importador.procesar().subscribe({
      next: () => this.procesando.set(false),
      error: () => this.procesando.set(false),
    });
  }

  volver(): void {
    void this.router.navigate(['/importador/origen']);
  }

  nuevaImportacion(): void {
    this.importador.resetear();
    void this.router.navigate(['/importador/subir']);
  }
}
