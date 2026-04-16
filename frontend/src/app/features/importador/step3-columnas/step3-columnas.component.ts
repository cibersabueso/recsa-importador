import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NgClass } from '@angular/common';
import { ImportadorService } from '../../../core/services/importador.service';
import { FileBadgeComponent } from '../../../shared/components/file-badge/file-badge.component';
import { CAMPOS_ESTANDAR, Mapeo, MapeoArchivo } from '../../../core/models/mapeo.model';

@Component({
  selector: 'app-step3-columnas',
  standalone: true,
  imports: [FormsModule, NgClass, FileBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="paso3">
      <section class="app-card seccion">
        <header class="seccion-header">
          <div>
            <h2>Revisar columnas</h2>
            <p class="subtitulo">
              Mapea cada columna del archivo origen al campo estándar del sistema RECSA.
            </p>
          </div>
        </header>

        @if (archivos().length > 1) {
          <div class="tabs" role="tablist">
            @for (a of archivos(); track a.id) {
              <button
                type="button"
                class="tab"
                role="tab"
                [attr.aria-selected]="a.id === archivoActivoId()"
                [ngClass]="{ activa: a.id === archivoActivoId() }"
                (click)="seleccionarArchivo(a.id)"
              >
                <span class="tab-num">{{ a.orden }}</span>
                <span class="tab-nombre">{{ a.nombre }}</span>
                <app-file-badge [tipo]="a.tipo" />
                @if (estadoArchivo(a.id) === 'completo') {
                  <span class="dot dot-ok"></span>
                } @else {
                  <span class="dot dot-warn"></span>
                }
              </button>
            }
          </div>
        }
      </section>

      @if (archivoActivo(); as archivo) {
        <section class="app-card seccion">
          <header class="seccion-header">
            <div>
              <h3>Campos estándar del sistema</h3>
              <p class="subtitulo">14 campos obligatorios que el sistema RECSA espera.</p>
            </div>
          </header>

          <div class="grid-campos">
            @for (campo of camposEstandar; track campo.nombre) {
              <div
                class="chip-campo"
                [ngClass]="{
                  cubierto: campoCubierto(campo.nombre),
                  faltante: esPrincipalActivo() && campo.obligatorio && !campoCubierto(campo.nombre)
                }"
              >
                <span class="chip-punto"></span>
                <span class="chip-nombre">{{ campo.etiqueta }}</span>
                @if (campo.obligatorio) {
                  <span class="chip-obligatorio">*</span>
                }
              </div>
            }
          </div>
        </section>

        @if (mapeoActivo()?.columnaClave === null) {
          <div class="alert alert-warning">
            <strong>Columna clave pendiente:</strong> selecciona la columna que se usará para
            vincular este archivo con los demás.
          </div>
        }

        @if (!esPrincipalActivo()) {
          <div class="alert alert-info">
            <strong>Archivo secundario:</strong> sólo la columna clave es obligatoria. Los
            campos estándar son opcionales y se cruzarán con el archivo principal cuando
            exista coincidencia.
          </div>
        }

        @if (faltantes().length > 0) {
          <section class="app-card seccion seccion-error">
            <header class="seccion-header">
              <div>
                <h3 class="titulo-error">
                  Campos obligatorios sin mapear ({{ faltantes().length }})
                </h3>
                <p class="subtitulo">Asigna estos campos para poder continuar.</p>
              </div>
            </header>
            <div class="chips-faltantes">
              @for (f of faltantes(); track f.nombre) {
                <span class="chip-faltante">{{ f.etiqueta }}</span>
              }
            </div>
          </section>
        }

        <section class="app-card seccion">
          <header class="seccion-header">
            <div>
              <h3>Mapeo de columnas</h3>
              <p class="subtitulo">Columna del archivo → Campo del sistema RECSA.</p>
            </div>
          </header>

          <ul class="lista-mapeos">
            @for (mp of mapeosActivos(); track mp.origen) {
              <li class="fila-mapeo">
                <div class="origen">
                  <span class="origen-label">Origen</span>
                  <span class="origen-nombre">{{ mp.origen }}</span>
                </div>
                <span class="flecha-mapeo">&rarr;</span>
                <div class="destino">
                  <span class="destino-label">Destino</span>
                  <select
                    class="form-control"
                    [ngModel]="mp.destino ?? ''"
                    (ngModelChange)="actualizarDestino(mp.origen, $event)"
                  >
                    <option value="">— Ignorar columna —</option>
                    @for (campo of camposEstandar; track campo.nombre) {
                      <option
                        [value]="campo.nombre"
                        [disabled]="destinoOcupadoPorOtro(campo.nombre, mp.origen)"
                      >
                        {{ campo.etiqueta }}{{ campo.obligatorio ? ' *' : '' }}
                      </option>
                    }
                  </select>
                </div>
                @if (mp.destino && campoObligatorio(mp.destino)) {
                  <span class="badge badge-configured">Obligatorio</span>
                }
              </li>
            }
          </ul>
        </section>

        <section class="app-card seccion">
          <header class="seccion-header">
            <div>
              <h3>Columna clave para vincular</h3>
              <p class="subtitulo">
                Selecciona la columna que identifica únicamente cada registro.
              </p>
            </div>
          </header>

          <div class="grid-clave">
            @for (col of archivo.columnas; track col) {
              <button
                type="button"
                class="boton-clave"
                [ngClass]="{ seleccionada: mapeoActivo()?.columnaClave === col }"
                (click)="seleccionarColumnaClave(col)"
              >
                {{ col }}
              </button>
            }
          </div>
        </section>

        <section class="app-card seccion">
          <header class="seccion-header">
            <div>
              <h3>Resumen</h3>
            </div>
          </header>
          <div class="grid-resumen">
            <div class="resumen-card-inner">
              <span class="resumen-num">{{ resumen().mapeadas }}</span>
              <span class="resumen-label">Columnas mapeadas</span>
            </div>
            <div class="resumen-card-inner">
              <span class="resumen-num" [ngClass]="{ malo: resumen().obligatoriasFaltan > 0 }">
                {{ resumen().obligatoriasCubiertas }}/{{ resumen().totalObligatorias }}
              </span>
              <span class="resumen-label">Obligatorias</span>
            </div>
            <div class="resumen-card-inner">
              <span class="resumen-num">{{ resumen().disponibles }}</span>
              <span class="resumen-label">Disponibles</span>
            </div>
          </div>
        </section>

        <section class="app-card seccion">
          <header class="seccion-header">
            <div>
              <h3>Vista previa con mapeo aplicado</h3>
              <p class="subtitulo">
                Azul: columna mapeada · Naranja: columna clave · Gris: columna sin mapear.
              </p>
            </div>
          </header>

          @if (archivo.columnas.length === 0) {
            <p class="sin-previa">Sin vista previa disponible para este archivo.</p>
          } @else {
            <div class="tabla-scroll">
              <table class="tabla-previa">
                <thead>
                  <tr>
                    @for (col of archivo.columnas; track col) {
                      <th
                        [ngClass]="{
                          mapeada: columnaMapeada(col),
                          clave: mapeoActivo()?.columnaClave === col
                        }"
                      >
                        <div class="th-contenido">
                          <span class="th-origen">{{ col }}</span>
                          @if (destinoPara(col); as dest) {
                            <span class="th-flecha">&darr;</span>
                            <span class="th-destino">{{ etiquetaCampo(dest) }}</span>
                          }
                        </div>
                      </th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (fila of archivo.previsualizacion; track $index) {
                    <tr>
                      @for (celda of fila; track $index; let colIdx = $index) {
                        <td
                          [ngClass]="{
                            mapeada: columnaMapeada(archivo.columnas[colIdx] ?? ''),
                            clave: mapeoActivo()?.columnaClave === archivo.columnas[colIdx]
                          }"
                        >
                          {{ celda }}
                        </td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </section>
      }

      <footer class="acciones">
        <button type="button" class="btn btn-ghost" (click)="volver()">Volver</button>
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
  `,
  styleUrl: './step3-columnas.component.scss',
})
export class Step3ColumnasComponent {
  private readonly importador = inject(ImportadorService);
  private readonly router = inject(Router);

  readonly archivos = this.importador.archivos;
  readonly mapeos = this.importador.mapeos;
  readonly puedeAvanzar = this.importador.puedeIrAPaso4;
  readonly camposEstandar = CAMPOS_ESTANDAR;

  readonly archivoActivoId = signal<string | null>(null);

  readonly archivoActivo = computed(() =>
    this.archivos().find((a) => a.id === this.archivoActivoId()) ?? null,
  );

  readonly mapeoActivo = computed<MapeoArchivo | null>(() => {
    const id = this.archivoActivoId();
    if (!id) return null;
    return this.mapeos().find((m) => m.archivoId === id) ?? null;
  });

  readonly mapeosActivos = computed<Mapeo[]>(() => this.mapeoActivo()?.mapeos ?? []);

  readonly esPrincipalActivo = computed(() => this.archivoActivo()?.orden === 1);

  readonly faltantes = computed(() => {
    const mp = this.mapeoActivo();
    if (!mp) return [];
    if (!this.esPrincipalActivo()) return [];
    return CAMPOS_ESTANDAR.filter(
      (c) => c.obligatorio && !mp.mapeos.some((m) => m.destino === c.nombre),
    );
  });

  readonly resumen = computed(() => {
    const mp = this.mapeoActivo();
    const totalObligatorias = CAMPOS_ESTANDAR.filter((c) => c.obligatorio).length;
    if (!mp) {
      return {
        mapeadas: 0,
        obligatoriasCubiertas: 0,
        obligatoriasFaltan: totalObligatorias,
        totalObligatorias,
        disponibles: this.archivoActivo()?.columnas.length ?? 0,
      };
    }
    const mapeadas = mp.mapeos.filter((m) => m.destino !== null).length;
    const obligatoriasCubiertas = CAMPOS_ESTANDAR.filter((c) => c.obligatorio).filter((c) =>
      mp.mapeos.some((m) => m.destino === c.nombre),
    ).length;
    return {
      mapeadas,
      obligatoriasCubiertas,
      obligatoriasFaltan: totalObligatorias - obligatoriasCubiertas,
      totalObligatorias,
      disponibles: mp.mapeos.length,
    };
  });

  constructor() {
    effect(() => {
      const archivos = this.archivos();
      if (archivos.length === 0) return;
      archivos.forEach((a) => this.importador.inicializarMapeoSiNecesario(a.id));
      if (this.archivoActivoId() === null) {
        this.archivoActivoId.set(archivos[0]!.id);
      }
    });
  }

  seleccionarArchivo(id: string): void {
    this.archivoActivoId.set(id);
  }

  actualizarDestino(origen: string, destino: string): void {
    const id = this.archivoActivoId();
    if (!id) return;
    this.importador.actualizarMapeo(id, origen, destino === '' ? null : destino);
  }

  seleccionarColumnaClave(columna: string): void {
    const id = this.archivoActivoId();
    if (!id) return;
    this.importador.definirColumnaClave(id, columna);
  }

  destinoOcupadoPorOtro(destino: string, origen: string): boolean {
    const mp = this.mapeoActivo();
    if (!mp) return false;
    return mp.mapeos.some((m) => m.destino === destino && m.origen !== origen);
  }

  campoObligatorio(nombre: string): boolean {
    return CAMPOS_ESTANDAR.find((c) => c.nombre === nombre)?.obligatorio ?? false;
  }

  campoCubierto(nombre: string): boolean {
    const mp = this.mapeoActivo();
    if (!mp) return false;
    return mp.mapeos.some((m) => m.destino === nombre);
  }

  columnaMapeada(columna: string): boolean {
    const mp = this.mapeoActivo();
    if (!mp) return false;
    return mp.mapeos.some((m) => m.origen === columna && m.destino !== null);
  }

  destinoPara(columna: string): string | null {
    const mp = this.mapeoActivo();
    if (!mp) return null;
    return mp.mapeos.find((m) => m.origen === columna)?.destino ?? null;
  }

  etiquetaCampo(nombre: string): string {
    return CAMPOS_ESTANDAR.find((c) => c.nombre === nombre)?.etiqueta ?? nombre;
  }

  estadoArchivo(id: string): 'completo' | 'incompleto' {
    const mp = this.mapeos().find((m) => m.archivoId === id);
    if (!mp) return 'incompleto';
    if (mp.columnaClave === null) return 'incompleto';
    const archivo = this.archivos().find((a) => a.id === id);
    if (archivo?.orden !== 1) return 'completo';
    const ok = CAMPOS_ESTANDAR.filter((c) => c.obligatorio).every((c) =>
      mp.mapeos.some((m) => m.destino === c.nombre),
    );
    return ok ? 'completo' : 'incompleto';
  }

  volver(): void {
    void this.router.navigate(['/importador/formato']);
  }

  continuar(): void {
    if (!this.puedeAvanzar()) return;
    this.importador.guardarMapeo().subscribe();
    void this.router.navigate(['/importador/origen']);
  }
}
