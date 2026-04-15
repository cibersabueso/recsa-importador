import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NgClass } from '@angular/common';
import { ImportadorService } from '../../../core/services/importador.service';
import { FileBadgeComponent } from '../../../shared/components/file-badge/file-badge.component';
import {
  ArchivoSubido,
  Codificacion,
  Delimitador,
  SeparadorDecimal,
} from '../../../core/models/archivo.model';
import {
  OPCIONES_CODIFICACION,
  OPCIONES_DELIMITADOR,
  OPCIONES_EMPRESA,
  OPCIONES_NOMBRE_INTERFAZ,
  OPCIONES_SEPARADOR_DECIMAL,
  OPCIONES_TIPO_CARGA,
  OPCIONES_TIPO_PROCESO,
} from '../../../core/models/config.model';

@Component({
  selector: 'app-step2-formato',
  standalone: true,
  imports: [FormsModule, NgClass, FileBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="paso2">
      <section class="app-card seccion">
        <header class="seccion-header">
          <div>
            <h2>Configuración del proceso</h2>
            <p class="subtitulo">Define el mandante, tipo de carga y responsable.</p>
          </div>
          @if (procesoGuardado()) {
            <span class="badge badge-configured">Guardado</span>
          }
        </header>

        <div class="grid-proceso">
          <div class="form-field">
            <label for="empresa">Empresa</label>
            <select
              id="empresa"
              class="form-control"
              [ngModel]="proceso().empresa"
              (ngModelChange)="actualizarProceso('empresa', $event)"
            >
              <option value="" disabled>Selecciona una empresa</option>
              @for (op of opcionesEmpresa; track op.valor) {
                <option [value]="op.valor">{{ op.etiqueta }}</option>
              }
            </select>
          </div>

          <div class="form-field">
            <label for="tipoCarga">Tipo de carga</label>
            <select
              id="tipoCarga"
              class="form-control"
              [ngModel]="proceso().tipoCarga"
              (ngModelChange)="actualizarProceso('tipoCarga', $event)"
            >
              <option value="" disabled>Selecciona el tipo de carga</option>
              @for (op of opcionesTipoCarga; track op.valor) {
                <option [value]="op.valor">{{ op.etiqueta }}</option>
              }
            </select>
          </div>

          <div class="form-field">
            <label for="tipoProceso">Tipo de proceso</label>
            <select
              id="tipoProceso"
              class="form-control"
              [ngModel]="proceso().tipoProceso"
              (ngModelChange)="actualizarProceso('tipoProceso', $event)"
            >
              <option value="" disabled>Selecciona el tipo de proceso</option>
              @for (op of opcionesTipoProceso; track op.valor) {
                <option [value]="op.valor">{{ op.etiqueta }}</option>
              }
            </select>
          </div>

          <div class="form-field">
            <label for="nombreInterfaz">Nombre de interfaz</label>
            <select
              id="nombreInterfaz"
              class="form-control"
              [ngModel]="proceso().nombreInterfaz"
              (ngModelChange)="actualizarProceso('nombreInterfaz', $event)"
            >
              <option value="" disabled>Selecciona una interfaz</option>
              @for (op of opcionesNombreInterfaz; track op.valor) {
                <option [value]="op.valor">{{ op.etiqueta }}</option>
              }
            </select>
          </div>

          <div class="form-field col-span-2">
            <label for="responsable">Responsable</label>
            <input
              id="responsable"
              type="text"
              class="form-control"
              placeholder="nombre.apellido"
              [ngModel]="proceso().responsable"
              (ngModelChange)="actualizarProceso('responsable', $event)"
            />
          </div>
        </div>

        <div class="acciones-inline">
          <button
            type="button"
            class="btn btn-primary"
            [disabled]="!procesoCompleto() || procesoGuardado()"
            (click)="guardarProceso()"
          >
            {{ procesoGuardado() ? 'Configuración guardada' : 'Guardar configuración' }}
          </button>
        </div>
      </section>

      <section class="app-card seccion">
        <header class="seccion-header">
          <div>
            <h2>Configuración de archivos</h2>
            <p class="subtitulo">
              Expande cada archivo para definir delimitador, codificación y encabezados.
            </p>
          </div>
          <div class="contador-archivos">
            {{ configuradosCount() }} / {{ archivos().length }} configurados
          </div>
        </header>

        <ul class="lista-archivos-config">
          @for (archivo of archivos(); track archivo.id; let idx = $index) {
            <li class="fila-archivo" [ngClass]="{ expandido: expandido() === archivo.id }">
              <div class="encabezado-fila" (click)="toggleExpandir(archivo.id)">
                <div class="orden-bloque">
                  <span class="numero-orden">{{ archivo.orden }}</span>
                  <div class="flechas">
                    <button
                      type="button"
                      class="flecha"
                      [disabled]="idx === 0"
                      (click)="mover(archivo.id, 'arriba', $event)"
                      aria-label="Subir"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                        <path
                          d="M6 15l6-6 6 6"
                          stroke="currentColor"
                          stroke-width="2.5"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="flecha"
                      [disabled]="idx === archivos().length - 1"
                      (click)="mover(archivo.id, 'abajo', $event)"
                      aria-label="Bajar"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                        <path
                          d="M6 9l6 6 6-6"
                          stroke="currentColor"
                          stroke-width="2.5"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                    </button>
                  </div>
                </div>

                <div class="nombre-bloque">
                  <div class="nombre-linea">
                    <span class="nombre">{{ archivo.nombre }}</span>
                    <app-file-badge [tipo]="archivo.tipo" />
                    @if (idx === 0) {
                      <span class="badge-principal">Principal</span>
                    }
                  </div>
                  <span class="detalle">
                    Delim:
                    <strong>{{ etiquetaDelim(archivo.delimitador) }}</strong> · Enc:
                    <strong>{{ archivo.codificacion }}</strong> ·
                    <strong>{{ archivo.tieneEncabezados ? 'Con encabezados' : 'Sin encabezados' }}</strong>
                  </span>
                </div>

                <div class="estado-bloque">
                  @if (archivo.estado === 'configurado') {
                    <span class="badge badge-configured">Configurado</span>
                  } @else {
                    <span class="badge badge-pending">Pendiente</span>
                  }
                  <span class="icono-toggle">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path
                        [attr.d]="expandido() === archivo.id ? 'M6 15l6-6 6 6' : 'M6 9l6 6 6-6'"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </span>
                </div>
              </div>

              @if (expandido() === archivo.id) {
                <div class="panel-config">
                  <div class="grid-config">
                    <div class="form-field">
                      <label>Delimitador</label>
                      <select
                        class="form-control"
                        [ngModel]="archivo.delimitador"
                        (ngModelChange)="cambiarDelimitador(archivo.id, $event)"
                      >
                        @for (op of opcionesDelim; track op.valor) {
                          <option [value]="op.valor">{{ op.etiqueta }}</option>
                        }
                      </select>
                    </div>

                    <div class="form-field">
                      <label>Separador decimal</label>
                      <select
                        class="form-control"
                        [ngModel]="archivo.separadorDecimal"
                        (ngModelChange)="cambiarSeparador(archivo.id, $event)"
                      >
                        @for (op of opcionesSep; track op.valor) {
                          <option [value]="op.valor">{{ op.etiqueta }}</option>
                        }
                      </select>
                    </div>

                    <div class="form-field">
                      <label>Codificación</label>
                      <select
                        class="form-control"
                        [ngModel]="archivo.codificacion"
                        (ngModelChange)="cambiarCodificacion(archivo.id, $event)"
                      >
                        @for (op of opcionesCod; track op.valor) {
                          <option [value]="op.valor">{{ op.etiqueta }}</option>
                        }
                      </select>
                    </div>

                    <label class="checkbox-encabezados">
                      <input
                        type="checkbox"
                        [checked]="archivo.tieneEncabezados"
                        (change)="cambiarEncabezados(archivo.id, $event)"
                      />
                      <span>La primera fila contiene encabezados</span>
                    </label>
                  </div>

                  <div class="previa-archivo">
                    <h4>Vista previa</h4>
                    @if (archivo.columnas.length === 0) {
                      <p class="sin-previa">Sin vista previa disponible para este archivo.</p>
                    } @else {
                      <div class="tabla-scroll">
                        <table class="tabla-previa">
                          <thead>
                            <tr>
                              @for (col of archivo.columnas; track col) {
                                <th>{{ col }}</th>
                              }
                            </tr>
                          </thead>
                          <tbody>
                            @for (fila of archivo.previsualizacion; track $index) {
                              <tr>
                                @for (celda of fila; track $index) {
                                  <td>{{ celda }}</td>
                                }
                              </tr>
                            }
                          </tbody>
                        </table>
                      </div>
                    }
                  </div>

                  <div class="acciones-inline">
                    <button
                      type="button"
                      class="btn btn-primary"
                      (click)="guardarArchivo(archivo.id)"
                    >
                      Guardar configuración
                    </button>
                  </div>
                </div>
              }
            </li>
          }
        </ul>
      </section>

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
  styleUrl: './step2-formato.component.scss',
})
export class Step2FormatoComponent {
  private readonly importador = inject(ImportadorService);
  private readonly router = inject(Router);

  readonly archivos = this.importador.archivos;
  readonly proceso = this.importador.proceso;
  readonly procesoGuardado = this.importador.procesoGuardado;
  readonly procesoCompleto = this.importador.procesoCompleto;
  readonly puedeAvanzar = this.importador.puedeIrAPaso3;

  readonly opcionesEmpresa = OPCIONES_EMPRESA;
  readonly opcionesTipoCarga = OPCIONES_TIPO_CARGA;
  readonly opcionesTipoProceso = OPCIONES_TIPO_PROCESO;
  readonly opcionesNombreInterfaz = OPCIONES_NOMBRE_INTERFAZ;
  readonly opcionesDelim = OPCIONES_DELIMITADOR;
  readonly opcionesSep = OPCIONES_SEPARADOR_DECIMAL;
  readonly opcionesCod = OPCIONES_CODIFICACION;

  readonly expandido = signal<string | null>(null);

  readonly configuradosCount = computed(
    () => this.archivos().filter((a) => a.estado === 'configurado').length,
  );

  actualizarProceso(campo: string, valor: string): void {
    this.importador.actualizarProceso({ [campo]: valor });
  }

  guardarProceso(): void {
    this.importador.guardarProceso().subscribe();
  }

  toggleExpandir(id: string): void {
    this.expandido.update((actual) => (actual === id ? null : id));
  }

  mover(id: string, dir: 'arriba' | 'abajo', e: Event): void {
    e.stopPropagation();
    this.importador.reordenarArchivo(id, dir);
  }

  cambiarDelimitador(id: string, valor: Delimitador): void {
    this.aplicarConfig(id, { delimitador: valor });
  }

  cambiarSeparador(id: string, valor: SeparadorDecimal): void {
    this.aplicarConfig(id, { separadorDecimal: valor });
  }

  cambiarCodificacion(id: string, valor: Codificacion): void {
    this.aplicarConfig(id, { codificacion: valor });
  }

  cambiarEncabezados(id: string, e: Event): void {
    const checked = (e.target as HTMLInputElement).checked;
    this.aplicarConfig(id, { tieneEncabezados: checked });
  }

  guardarArchivo(id: string): void {
    this.importador.guardarConfiguracionArchivo(id).subscribe();
    this.expandido.set(null);
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

  volver(): void {
    void this.router.navigate(['/importador/subir']);
  }

  continuar(): void {
    if (!this.puedeAvanzar()) return;
    void this.router.navigate(['/importador/columnas']);
  }

  private aplicarConfig(
    id: string,
    parcial: Partial<{
      delimitador: Delimitador;
      separadorDecimal: SeparadorDecimal;
      codificacion: Codificacion;
      tieneEncabezados: boolean;
    }>,
  ): void {
    const actual = this.archivos().find((a) => a.id === id);
    if (!actual) return;
    this.importador.actualizarConfiguracionArchivo(id, {
      delimitador: parcial.delimitador ?? actual.delimitador,
      separadorDecimal: parcial.separadorDecimal ?? actual.separadorDecimal,
      codificacion: parcial.codificacion ?? actual.codificacion,
      tieneEncabezados: parcial.tieneEncabezados ?? actual.tieneEncabezados,
    });
  }

  trackArchivo(_: number, a: ArchivoSubido): string {
    return a.id;
  }
}
